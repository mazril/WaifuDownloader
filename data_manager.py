# -*- coding: utf-8 -*-
import os
import json
import logging
import time 
import random 

import db_manager 
import config_handler 
import utils 
import constants 
import reporting 
from driver_utils import scroll_until_timeout 
from services import download_image as service_download_image 


logger = logging.getLogger(__name__)

def get_model_data_dir(model_name_sanitized): 
    base_dir_to_use = constants.BASE_DATA_DIR 
    os.makedirs(base_dir_to_use, exist_ok=True) 
    return os.path.join(base_dir_to_use, model_name_sanitized)

def download_gallery(driver, gallery_url, gallery_save_path, gallery_id, model_name, 
                     shutdown_flag_func=None, prefetched_image_urls=None):
    """
    Pobiera pliki dla galerii, zliczając błędy i potencjalnie wyłączając ją.

    Opis modyfikacji:
    - Dodano licznik błędów `consecutive_errors`.
    - Wczytuje próg błędów `max_errors` z `config.json`.
    - Jeśli galeria jest pusta (brak plików w folderze i w DB), a liczba błędów
      pobierania osiągnie próg, funkcja przerywa pracę i zwraca flagę
      `was_disabled`, informującą o konieczności wyłączenia galerii.
    - Licznik błędów jest resetowany po każdym udanym pobraniu.

    Wpływ na inne funkcje:
    - `processing.py` musi teraz obsłużyć nową flagę `was_disabled` w odpowiedzi
      z tej funkcji.
    """
    logger.info(f"Rozpoczynam pobieranie galerii: {gallery_id} ({gallery_url}) do {gallery_save_path}")
    
    gallery_data_from_db = db_manager.get_gallery(gallery_id) 
    initial_downloaded_count_from_db = gallery_data_from_db.get('downloaded_count', 0) if gallery_data_from_db else 0
    expected_count_from_db = gallery_data_from_db.get('expected_count') if gallery_data_from_db else None
    gallery_title_for_reporting = gallery_data_from_db.get('determined_title') or gallery_data_from_db.get('original_title') or gallery_id if gallery_data_from_db else gallery_id

    os.makedirs(gallery_save_path, exist_ok=True)
    
    try:
        existing_files = {f for f in os.listdir(gallery_save_path) if os.path.isfile(os.path.join(gallery_save_path, f))}
    except FileNotFoundError:
        existing_files = set()
    
    current_files_in_folder_count = len(existing_files)
    logger.info(f"W folderze '{gallery_save_path}' znajduje się {current_files_in_folder_count} plików (DB: {initial_downloaded_count_from_db}).")

    image_links_to_process = []
    total_images_on_page = 0

    if prefetched_image_urls is not None:
        logger.info(f"Używam {len(prefetched_image_urls)} wcześniej zebranych linków dla galerii {gallery_id}.")
        image_links_to_process = prefetched_image_urls
        total_images_on_page = len(image_links_to_process)
    else:
        logger.info(f"Brak wcześniej zebranych linków dla galerii {gallery_id}. Skanuję stronę.")
        if not driver_utils.is_url_loaded(driver, gallery_url):
             driver_utils.safe_driver_get(driver, gallery_url, shutdown_flag_func=shutdown_flag_func)

        image_link_elements = scroll_until_timeout( 
            driver, 'div.photo-item a[href]', 
            expected_count=expected_count_from_db, gallery_id=gallery_id,
            model_name=model_name, gallery_title=gallery_title_for_reporting,
            shutdown_flag_func=shutdown_flag_func
        )
        if image_link_elements:
            image_links_to_process = [el.get_attribute('href') for el in image_link_elements if el.get_attribute('href')]
            total_images_on_page = len(image_links_to_process)
        else:
            logger.warning(f"Nie znaleziono żadnych linków do obrazów (scroll_until_timeout) dla galerii {gallery_id}.")

    if not image_links_to_process:
        logger.warning(f"Brak linków do obrazów do przetworzenia dla galerii {gallery_id}.")
        final_status_no_links = 'completed' if expected_count_from_db == 0 else 'error'
        if expected_count_from_db is None and current_files_in_folder_count > 0:
            final_status_no_links = 'downloaded_unknown_total'
        elif expected_count_from_db is None and current_files_in_folder_count == 0:
             final_status_no_links = 'pending_check' 

        db_manager.update_gallery(gallery_id, downloaded_count=current_files_in_folder_count, status=final_status_no_links, expected_count=expected_count_from_db or 0)
        return {'downloaded_count': current_files_in_folder_count, 'expected_count': expected_count_from_db or 0, 'was_disabled': False}

    if expected_count_from_db is None or total_images_on_page > expected_count_from_db:
        logger.info(f"Aktualizuję expected_count dla {gallery_id} z {expected_count_from_db} na {total_images_on_page}")
        db_manager.update_gallery(gallery_id, expected_count=total_images_on_page) 
        expected_count_from_db = total_images_on_page 

    newly_downloaded_this_session = 0
    actual_downloaded_for_loop = current_files_in_folder_count
    
    # Nowa logika do obsługi błędów
    consecutive_errors = 0
    max_errors = config_handler.current_config['downloading']['max_consecutive_download_errors']['value']
    gallery_was_empty = (initial_downloaded_count_from_db == 0 and current_files_in_folder_count == 0)
    gallery_should_be_disabled = False

    for i, image_url in enumerate(image_links_to_process):
        if shutdown_flag_func and shutdown_flag_func():
            logger.info("Zatrzymano pobieranie galerii z powodu żądania zamknięcia.")
            break
        try:
            if not image_url or not image_url.startswith('http'):
                logger.warning(f"Pominięto nieprawidłowy URL obrazka: {image_url}")
                continue

            image_filename = os.path.basename(utils.urlparse(image_url).path) 
            if not image_filename:
                image_filename = f"image_{i+1}.jpg" 
                logger.warning(f"Nie udało się uzyskać nazwy pliku z URL: {image_url}. Używam: {image_filename}")

            if image_filename in existing_files:
                logger.debug(f"Plik {image_filename} już istnieje ({i+1}/{total_images_on_page}). Pomijam.")
                continue

            filepath = os.path.join(gallery_save_path, image_filename)
            
            if service_download_image(image_url, filepath): 
                consecutive_errors = 0 # Resetuj licznik po sukcesie
                actual_downloaded_for_loop += 1
                newly_downloaded_this_session += 1
                existing_files.add(image_filename)
                logger.info(f"Pobrano {actual_downloaded_for_loop}/{expected_count_from_db or '?'} - {image_filename} (sesja: {newly_downloaded_this_session})")
                reporting.update_current_status( 
                    message=f"Pobieranie... {actual_downloaded_for_loop}/{expected_count_from_db or '?'}",
                    model=model_name, gallery=gallery_title_for_reporting,
                    gallery_id=gallery_id, downloaded_count=actual_downloaded_for_loop,
                    expected_count=expected_count_from_db, is_processing=True
                )
            else:
                logger.error(f"Nie udało się pobrać obrazka: {image_url}")
                consecutive_errors += 1
                if gallery_was_empty and consecutive_errors >= max_errors:
                    logger.critical(f"Galeria {gallery_id} była pusta i osiągnęła próg {max_errors} błędów pobierania. Zostanie wyłączona.")
                    gallery_should_be_disabled = True
                    break # Przerwij pętlę pobierania dla tej galerii

        except Exception as e:
            logger.error(f"Błąd podczas pobierania obrazka {image_url}: {e}", exc_info=True)
            consecutive_errors += 1
            if gallery_was_empty and consecutive_errors >= max_errors:
                logger.critical(f"Galeria {gallery_id} (pusta) osiągnęła próg {max_errors} błędów (wyjątek w pętli). Zostanie wyłączona.")
                gallery_should_be_disabled = True
                break

    final_downloaded_count_in_folder = len(os.listdir(gallery_save_path))
    logger.info(f"Zakończono pętlę pobierania dla galerii {gallery_id}. Pobranych w tej sesji: {newly_downloaded_this_session}. Łącznie w folderze: {final_downloaded_count_in_folder}.")
    
    return {
        'downloaded_count': final_downloaded_count_in_folder, 
        'expected_count': expected_count_from_db or total_images_on_page,
        'was_disabled': gallery_should_be_disabled
    }