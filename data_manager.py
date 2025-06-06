# -*- coding: utf-8 -*-
import os
import json
import logging
import time 
import random 
from urllib.parse import urlparse

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
    Pobiera obrazy dla danej galerii.
    
    Opis modyfikacji:
    - Dodano walidację nazwy pliku obrazka. Jeśli nazwa zaczyna się od znaku '-',
      link jest ignorowany, a w logach pojawia się ostrzeżenie.
      
    Wpływ na inne funkcje:
    - Zapobiega błędom i próbom pobierania plików z ewidentnie uszkodzonych linków,
      co zwiększa stabilność procesu pobierania.
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

    image_links_to_process = prefetched_image_urls if prefetched_image_urls is not None else []
    total_images_on_page = len(image_links_to_process)

    if not image_links_to_process:
        logger.warning(f"Brak linków do obrazów do przetworzenia dla galerii {gallery_id} (prefetched).")
        # Logika dla braku linków...
        return {'downloaded_count': current_files_in_folder_count, 'expected_count': expected_count_from_db or 0}

    if expected_count_from_db is None or total_images_on_page > expected_count_from_db:
        logger.info(f"Aktualizuję expected_count dla {gallery_id} z {expected_count_from_db} na {total_images_on_page}")
        db_manager.update_gallery(gallery_id, expected_count=total_images_on_page) 
        expected_count_from_db = total_images_on_page

    newly_downloaded_this_session = 0
    actual_downloaded_for_loop = current_files_in_folder_count 

    for i, image_url in enumerate(image_links_to_process):
        if shutdown_flag_func and shutdown_flag_func():
            logger.info("Zatrzymano pobieranie galerii z powodu żądania zamknięcia.")
            break
        try:
            if not image_url or not image_url.startswith('http'):
                logger.warning(f"Pominięto nieprawidłowy URL obrazka: {image_url}")
                continue

            image_filename = os.path.basename(urlparse(image_url).path)

            # --- NOWA WALIDACJA LINKU ---
            if not image_filename or image_filename.startswith('-'):
                logger.warning(f"Pominięto nieprawidłowy link do obrazka (nazwa pliku pusta lub zaczyna się od '-'): {image_url}")
                continue
            # --- KONIEC NOWEJ WALIDACJI ---

            if image_filename in existing_files:
                logger.debug(f"Plik {image_filename} już istnieje ({i+1}/{total_images_on_page}). Pomijam.")
                continue

            filepath = os.path.join(gallery_save_path, image_filename)
            
            if service_download_image(image_url, filepath): 
                actual_downloaded_for_loop += 1
                newly_downloaded_this_session += 1
                existing_files.add(image_filename)
                logger.info(f"Pobrano {actual_downloaded_for_loop}/{expected_count_from_db or '?'} - {image_filename} (sesja: {newly_downloaded_this_session})")
                reporting.update_current_status( 
                    message=f"Pobieranie... {actual_downloaded_for_loop}/{expected_count_from_db or '?'}",
                    model=model_name, gallery=gallery_title_for_reporting, gallery_id=gallery_id,
                    downloaded_count=actual_downloaded_for_loop, expected_count=expected_count_from_db,
                    is_processing=True
                )
            else:
                logger.error(f"Nie udało się pobrać obrazka: {image_url}")
        except Exception as e:
            logger.error(f"Błąd podczas pobierania obrazka {image_url}: {e}", exc_info=True)

    final_downloaded_count_in_folder = len(os.listdir(gallery_save_path))
    logger.info(f"Zakończono pętlę pobierania dla galerii {gallery_id}. Pobranych w tej sesji: {newly_downloaded_this_session}. Łącznie w folderze: {final_downloaded_count_in_folder}.")
    
    return {'downloaded_count': final_downloaded_count_in_folder, 'expected_count': expected_count_from_db or total_images_on_page}