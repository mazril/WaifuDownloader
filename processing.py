# processing.py
# -*- coding: utf-8 -*-
import os
import time
import random
import traceback
import re
import json
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException, JavascriptException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging

import constants
import config_handler
import utils
import db_manager
import driver_utils
import reporting
# Import funkcji pobierającej z data_manager
from data_manager import download_gallery as dm_download_gallery 

logger = logging.getLogger(__name__)

def _is_shutdown_requested_processing(shutdown_flag_func=None):
    if shutdown_flag_func:
        return shutdown_flag_func()
    try:
        from __main__ import shutdown_requested as main_shutdown_flag
        return main_shutdown_flag
    except ImportError:
        logger.warning("Nie można zaimportować shutdown_requested z __main__ w processing.py. "
                       "Funkcje wymagające tej flagi mogą nie działać poprawnie bez przekazania argumentu shutdown_flag_func.")
        return False


def _extract_title_from_scripts(driver):
    logger.info("Próba ekstrakcji tytułu z tagów <script> na stronie galerii...")
    try:
        scripts_content = driver.execute_script(
            "return Array.from(document.querySelectorAll('script')).map(s => s.innerHTML).join('\\n');"
        )
        if scripts_content:
            match = re.search(r"(?:const|let|var)\s+title\s*=\s*[\"']([^\"']+)[\"']\s*;", scripts_content)
            if match:
                extracted_title = match.group(1).strip()
                logger.info(f"Znaleziono deklarację 'title' w skryptach: \"{extracted_title}\"")
                return extracted_title
            else:
                logger.debug("Nie znaleziono pasującej deklaracji 'const/let/var title = \"...\"' w tagach <script>.")
        else:
            logger.debug("Nie znaleziono zawartości w tagach <script> na stronie.")
    except Exception as e:
        logger.error(f"Błąd podczas próby ekstrakcji tytułu z tagów <script>: {e}", exc_info=False)
    return None

def _get_gallery_page_title_candidate(driver):
    script_title = _extract_title_from_scripts(driver)
    if script_title:
        logger.info(f"Używam tytułu ze skryptu: \"{script_title}\"")
        return script_title
    logger.info("Nie udało się wyekstrahować tytułu ze skryptów. Próbuję z elementu H1.")
    try:
        title_elements_h1 = driver.find_elements(By.XPATH, "//h1[contains(@class, 'text-center') and contains(@class, 'text-uppercase') and contains(@class, 'h6')] | //h1[1]")
        if title_elements_h1:
            raw_h1_title = title_elements_h1[0].text.strip()
            logger.info(f"Pobrano surowy tytuł z elementu H1: \"{raw_h1_title}\"")
            cleaned_title = re.sub(r"^\s*YOU MAY ALSO LIKE:\s*", "", raw_h1_title, flags=re.IGNORECASE)
            cleaned_title = re.sub(r"\s*-\s*\d+\s*(photos|images|pics|leaked|leaks|nude|nudes|video|videos|onlyfans|patreon|fansly|reddit|telegram|sets|vids|файлов).*", "", cleaned_title, flags=re.IGNORECASE)
            cleaned_title = re.sub(r"\s*-\s*\d+$", "", cleaned_title).strip()
            if cleaned_title: logger.info(f"Oczyszczony tytuł z H1: \"{cleaned_title}\""); return cleaned_title
    except NoSuchElementException: logger.info("Nie znaleziono oczekiwanego elementu H1 dla tytułu galerii.")
    except Exception as e: logger.warning(f"Błąd podczas próby pobrania i oczyszczenia tytułu z H1: {e}")
    logger.info("Nie udało się uzyskać satysfakcjonującego tytułu ze strony galerii."); return None

def _extract_cosplay_fandom_tags(driver):
    cosplay_tags, fandom_tags = [], []
    try:
        tag_elements = driver.find_elements(By.CSS_SELECTOR, "a.btn[href*='/cosplay/'], a.btn[href*='/fandom/']")
        if not tag_elements:
             tag_elements = driver.find_elements(By.XPATH, "//center//a[contains(@class, 'btn') and (contains(@href, '/cosplay/') or contains(@href, '/fandom/'))]")
        for tag_el in tag_elements:
            href, text = tag_el.get_attribute('href'), tag_el.text.strip()
            if href and text:
                if '/cosplay/' in href: cosplay_tags.append(text)
                elif '/fandom/' in href: fandom_tags.append(text)
        if cosplay_tags: logger.info(f"Znaleziono tagi cosplay: {list(set(cosplay_tags))}")
        if fandom_tags: logger.info(f"Znaleziono tagi fandom: {list(set(fandom_tags))}")
    except Exception as e: logger.warning(f"Błąd ekstrakcji tagów cosplay/fandom: {e}", exc_info=False)
    return list(set(cosplay_tags)), list(set(fandom_tags))

def _get_gallery_description(driver):
    """
    Pobiera opis galerii z dedykowanego kontenera na stronie.
    Opis: Nowa funkcja do ekstrakcji opisu tekstowego galerii. Szuka ona 
          elementu <div class="container mb-1"> i pobiera jego zawartość tekstową.
    Wpływ na inne funkcje: Wynik tej funkcji jest zapisywany w nowej kolumnie 
                           `gallery_description` w bazie danych.
    """
    logger.info("Próba ekstrakcji opisu z <div class='container mb-1'>...")
    try:
        description_element = driver.find_element(By.CSS_SELECTOR, "div.container.mb-1")
        if description_element and description_element.text:
            desc_text = description_element.text.strip()
            logger.info(f"Znaleziono opis galerii: '{desc_text[:120]}...'")
            return desc_text
    except NoSuchElementException:
        logger.info("Nie znaleziono elementu opisu galerii ('div.container.mb-1').")
        return None
    except Exception as e:
        logger.error(f"Błąd podczas ekstrakcji opisu galerii: {e}", exc_info=False)
        return None
    return None

def _get_tags_from_db(gallery_id):
    try:
        gallery_data = db_manager.get_gallery(gallery_id)
        if gallery_data and gallery_data.get('tags_json'):
            tags_str = gallery_data['tags_json']
            if isinstance(tags_str, str):
                try:
                    tags = json.loads(tags_str)
                except json.JSONDecodeError:
                    logger.warning(f"Błąd dekodowania JSON tagów dla {gallery_id}: {tags_str}")
                    return [], []
            elif isinstance(tags_str, dict):
                 tags = tags_str
            else:
                 logger.error(f"Nieznany typ danych dla tags_json {gallery_id}: {type(tags_str)}")
                 return [], []
            return tags.get("cosplay", []), tags.get("fandom", [])
    except Exception as e:
        logger.error(f"Błąd pobierania tagów z DB dla {gallery_id}: {e}")
    return [], []

def _scan_new_model_page(driver, model_name_original, shutdown_flag_func=None):
    logger.info(f"Rozpoczynam skanowanie strony dla modelki: {model_name_original}")
    model_id = db_manager.get_or_create_model(model_name_original)
    if not model_id: logger.error(f"Nie udało się uzyskać/stworzyć ID dla modelki {model_name_original}."); return []
    
    sanitized_model_name_for_url = utils.sanitize_foldername(model_name_original).lower().replace('_', '-')
    model_url = f"{constants.BASE_URL_SITE}/model/{sanitized_model_name_for_url}"
    try:
        driver_utils.safe_driver_get(driver, model_url, shutdown_flag_func=shutdown_flag_func)
        logger.info(f"Strona modelki '{model_name_original}' ({model_url}) załadowana.")
        gallery_link_selector = "a[href*='/gallery/'][class*='text-white']"
        
        link_elements = driver_utils.scroll_until_timeout(
            driver, gallery_link_selector, expected_count=None, allow_up_scroll=True,
            gallery_id=f"scan_{utils.sanitize_foldername(model_name_original)}",
            model_name=model_name_original, gallery_title="Skanowanie strony modelki",
            shutdown_flag_func=shutdown_flag_func
        )
        if not link_elements: logger.warning(f"Nie znaleziono elementów galerii dla '{model_name_original}'."); return []
        logger.info(f"Znaleziono {len(link_elements)} potencjalnych linków/tytułów. Przetwarzam...")
        processed_urls = set()
        for idx, link_el in enumerate(link_elements):
            if _is_shutdown_requested_processing(shutdown_flag_func): break
            gallery_url_attr = "Nieznany"
            try:
                gallery_url_attr = link_el.get_attribute('href')
                if not gallery_url_attr or '/gallery/' not in gallery_url_attr or gallery_url_attr in processed_urls: continue
                processed_urls.add(gallery_url_attr)
                gallery_id_from_url = utils.get_gallery_id(gallery_url_attr)
                if not gallery_id_from_url or gallery_id_from_url.startswith("error_"): continue
                original_title_from_scan = link_el.text.strip() or gallery_id_from_url
                expected_count_from_scan = None
                try:
                    grid_item_container = link_el.find_element(By.XPATH, "./ancestor::div[contains(@class, 'grid-item')]")
                    if grid_item_container:
                        count_text = grid_item_container.find_element(By.CSS_SELECTOR, "span.ms-1").text.strip()
                        if count_text.isdigit(): expected_count_from_scan = int(count_text)
                except: pass
                gallery_data = {"gallery_id": gallery_id_from_url, "model_id": model_id, "url": gallery_url_attr,
                                "original_title": original_title_from_scan,
                                "expected_count": expected_count_from_scan,
                                "status": "pending_check", 
                                "initial_data_fetched": False } 
                db_manager.update_gallery_smart(gallery_data, only_if_newer_scan_data=True)
            except Exception as e: logger.warning(f"Błąd przetwarzania linku #{idx+1} ({gallery_url_attr}): {e}", exc_info=False)
        logger.info(f"Zakończono skanowanie dla '{model_name_original}'.")
    except constants.RestartRequiredError: raise
    except Exception as e: logger.exception(f"Krytyczny błąd skanowania strony modelki {model_name_original}: {e}")


def process_single_gallery(driver, model_name_original, gallery_url, gallery_id_input,
                           fetch_only_initial_data=False,
                           task_payload_for_triggers=None,
                           shutdown_flag_func=None,
                           collected_gallery_image_links_ref=None): # Słownik przekazywany przez referencję
    
    logger.info(f"PSG_START ({gallery_id_input}): Rozpoczynam przetwarzanie. fetch_only_initial_data: {fetch_only_initial_data}")
    config_handler.load_config()
    gallery_entry_db = db_manager.get_gallery(gallery_id_input) 
    
    if not gallery_entry_db:
        logger.error(f"PSG_ERROR ({gallery_id_input}): Nie udało się pobrać danych galerii z DB! Pomijam.")
        return False

    model_name_from_db = gallery_entry_db.get('model_name', model_name_original)
    current_original_title_from_db = gallery_entry_db.get("original_title") or gallery_id_input
    determined_title_from_db = gallery_entry_db.get("determined_title")
    sanitized_model_name = gallery_entry_db.get('sanitized_name') or utils.sanitize_foldername(model_name_from_db)
    title_for_reporting = determined_title_from_db or gallery_entry_db.get("source_page_title") or current_original_title_from_db or gallery_id_input
    
    page_already_loaded_this_call = False

    try:
        # --- Krok 1: Pobieranie danych inicjalnych (jeśli potrzebne) ---
        if not gallery_entry_db.get('initial_data_fetched'):
            logger.info(f"PSG ({gallery_id_input}): Wymagane pobranie danych inicjalnych ze strony.")
            reporting.update_current_status(
                message=f"Pobieranie danych inicjalnych...", model=model_name_from_db, gallery=title_for_reporting,
                gallery_id=gallery_id_input, is_processing=True
            )
            driver_utils.safe_driver_get(driver, gallery_url, shutdown_flag_func=shutdown_flag_func)
            page_already_loaded_this_call = True

            page_derived_title_candidate = _get_gallery_page_title_candidate(driver)
            cosplay_tags_list, fandom_tags_list = _extract_cosplay_fandom_tags(driver)
            gallery_description_text = _get_gallery_description(driver)
            
            updates_for_db_initial = {'initial_data_fetched': True, 'last_processed_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')}
            if page_derived_title_candidate:
                updates_for_db_initial['source_page_title'] = page_derived_title_candidate
                if not gallery_entry_db.get('original_title'):
                    updates_for_db_initial['original_title'] = page_derived_title_candidate
            if gallery_description_text:
                updates_for_db_initial['gallery_description'] = gallery_description_text
            if cosplay_tags_list or fandom_tags_list:
                updates_for_db_initial['tags_json'] = {"cosplay": cosplay_tags_list, "fandom": fandom_tags_list}
            
            db_manager.update_gallery(gallery_id_input, **updates_for_db_initial)
            gallery_entry_db = db_manager.get_gallery(gallery_id_input) # Odśwież dane
            if not gallery_entry_db:
                logger.error(f"PSG_ERROR ({gallery_id_input}): Nie udało się odświeżyć danych galerii po aktualizacji danych inicjalnych."); return False

            title_for_reporting = gallery_entry_db.get("determined_title") or gallery_entry_db.get("source_page_title") or gallery_entry_db.get("original_title") or gallery_id_input
            logger.info(f"PSG ({gallery_id_input}): Dane inicjalne pobrane. source_page_title: '{gallery_entry_db.get('source_page_title')}'")

        # --- Krok 1.5: Obsługa trybu fetch_only_initial_data ---
        if fetch_only_initial_data:
            logger.info(f"PSG ({gallery_id_input}): Tryb 'fetch_only_initial_data' aktywny.")
            if task_payload_for_triggers:
                trigger_action = task_payload_for_triggers.get('trigger_action_after_fetch')
                new_status_for_trigger = None
                fields_to_nullify = {}

                if trigger_action == 'production_ai': 
                    new_status_for_trigger = 'pending_production_ai'
                    fields_to_nullify['determined_title'] = None
                elif trigger_action == 'test_ai': 
                    new_status_for_trigger = 'pending_test_ai'
                    fields_to_nullify['test_ai_title'] = None
                
                if new_status_for_trigger:
                    logger.info(f"PSG ({gallery_id_input}): Ustawiam status na '{new_status_for_trigger}' i zeruję odpowiednie tytuły AI.")
                    db_manager.update_gallery(gallery_id_input, status=new_status_for_trigger, **fields_to_nullify)
                else:
                    logger.warning(f"PSG ({gallery_id_input}): Nieznany trigger '{trigger_action}' w 'fetch_only_initial_data'. Status pozostaje '{gallery_entry_db.get('status')}'.")
            else:
                logger.warning(f"PSG ({gallery_id_input}): fetch_only_initial_data=True, ale brak task_payload_for_triggers. Status pozostaje '{gallery_entry_db.get('status')}'.")
            
            reporting.update_current_status("Zakończono pobieranie danych inicjalnych (tryb specjalny).", model=model_name_from_db, gallery=title_for_reporting, gallery_id=gallery_id_input, is_processing=False)
            return True

        # --- Krok 2: Ustalanie czy potrzebujemy tytułu od AI i czy mamy linki ---
        needs_ai_title = not gallery_entry_db.get('determined_title')
        current_status = gallery_entry_db.get('status')
        is_ai_pending_or_error = current_status in ['pending_production_ai', 'pending_test_ai', 'pending_initial_fetch_prod_ai', 'pending_initial_fetch_test_ai', 'error_ai_prod', 'error_ai_test', 'error_ai']
        
        links_are_collected_in_memory = False
        if collected_gallery_image_links_ref is not None and gallery_id_input in collected_gallery_image_links_ref:
            links_are_collected_in_memory = True
            logger.info(f"PSG_DEBUG ({gallery_id_input}): Linki są już w pamięci podręcznej. Liczba: {len(collected_gallery_image_links_ref[gallery_id_input])}")

        # --- Krok 3: Zbieranie linków i/lub zlecanie AI ---
        if needs_ai_title and not is_ai_pending_or_error:
            logger.info(f"PSG ({gallery_id_input}): Brak 'determined_title', status '{current_status}' nie wskazuje na oczekiwanie na AI. Ustawiam 'pending_production_ai'.")
            db_manager.update_gallery(gallery_id_input, status='pending_production_ai')
            gallery_entry_db = db_manager.get_gallery(gallery_id_input)
            current_status = gallery_entry_db.get('status')
            is_ai_pending_or_error = True 
            reporting.update_current_status(
                message="Oczekuje na AI (Prod.)...", model=model_name_from_db, gallery=title_for_reporting,
                gallery_id=gallery_id_input, is_processing=True
            )
        
        should_collect_links_now = False
        if needs_ai_title and is_ai_pending_or_error and not links_are_collected_in_memory:
            should_collect_links_now = True
            logger.info(f"PSG ({gallery_id_input}): Potrzebny tytuł AI i linki nie są zebrane. Będę zbierać linki.")
        elif not needs_ai_title and not links_are_collected_in_memory and current_status not in ['completed', 'completed_with_tolerance']:
            should_collect_links_now = True
            logger.info(f"PSG ({gallery_id_input}): Tytuł AI jest, ale linki nie są zebrane. Będę zbierać linki.")

        if should_collect_links_now:
            if not page_already_loaded_this_call:
                if driver_utils.is_url_loaded(driver, gallery_url):
                    logger.info(f"PSG ({gallery_id_input}): Driver jest już na stronie {gallery_url}. Nie ładuję ponownie.")
                else:
                    logger.info(f"PSG ({gallery_id_input}): Strona nie była ładowana w tej sesji. Ładuję: {gallery_url}")
                    driver_utils.safe_driver_get(driver, gallery_url, shutdown_flag_func=shutdown_flag_func)
                    page_already_loaded_this_call = True
            
            logger.info(f"PSG ({gallery_id_input}): Rozpoczynam zbieranie linków do obrazów.")
            image_link_elements = driver_utils.scroll_until_timeout(
                driver, 'div.photo-item a[href]', 
                expected_count=gallery_entry_db.get('expected_count'), 
                gallery_id=gallery_id_input, model_name=model_name_from_db, 
                gallery_title=title_for_reporting,
                initial_downloaded_count=gallery_entry_db.get('downloaded_count', 0),
                current_expected_count_for_reporting=gallery_entry_db.get('expected_count'),
                shutdown_flag_func=shutdown_flag_func
            )
            if collected_gallery_image_links_ref is not None:
                hrefs = [el.get_attribute('href') for el in image_link_elements if el.get_attribute('href')]
                collected_gallery_image_links_ref[gallery_id_input] = hrefs
                links_are_collected_in_memory = True
                logger.info(f"PSG ({gallery_id_input}): Zebrano i przechowano {len(hrefs)} linków w pamięci.")
            else:
                logger.warning(f"PSG ({gallery_id_input}): `collected_gallery_image_links_ref` jest None. Nie można przechować linków.")

            total_images_on_page_from_scan = len(image_link_elements)
            current_expected_db = gallery_entry_db.get('expected_count')
            if current_expected_db is None or total_images_on_page_from_scan > current_expected_db:
                logger.info(f"PSG ({gallery_id_input}): Aktualizuję expected_count z {current_expected_db} na {total_images_on_page_from_scan}.")
                db_manager.update_gallery(gallery_id_input, expected_count=total_images_on_page_from_scan)
                gallery_entry_db = db_manager.get_gallery(gallery_id_input)

        if needs_ai_title and is_ai_pending_or_error:
            logger.info(f"PSG ({gallery_id_input}): Oczekuję na wygenerowanie nazwy przez AI (status: {current_status}). Linki zebrane: {'Tak' if links_are_collected_in_memory else 'Nie'}. Kończę cykl.")
            return True 

        # --- Krok 4: Mamy tytuł od AI, czas na folder i pobieranie ---
        title_for_folder_creation = gallery_entry_db.get("determined_title") or gallery_entry_db.get("source_page_title") or gallery_entry_db.get("original_title") or gallery_id_input
        sanitized_folder_base = utils.sanitize_foldername(title_for_folder_creation)
        model_base_data_dir = os.path.join(constants.BASE_DATA_DIR, sanitized_model_name)
        os.makedirs(model_base_data_dir, exist_ok=True)

        gallery_folder_path_from_db = gallery_entry_db.get("folder_path")
        expected_folder_full_path = os.path.join(model_base_data_dir, sanitized_folder_base)
        final_gallery_folder_path = gallery_folder_path_from_db
        
        path_needs_update_or_creation = False
        if not gallery_folder_path_from_db:
            path_needs_update_or_creation = True
        elif os.path.normpath(gallery_folder_path_from_db) != os.path.normpath(expected_folder_full_path):
            if os.path.basename(gallery_folder_path_from_db) != sanitized_folder_base and os.path.dirname(gallery_folder_path_from_db) == model_base_data_dir:
                path_needs_update_or_creation = True
            elif os.path.dirname(gallery_folder_path_from_db) != model_base_data_dir:
                 path_needs_update_or_creation = True

        if path_needs_update_or_creation:
            path_candidate = expected_folder_full_path
            counter = 1
            while os.path.exists(path_candidate) and (not gallery_folder_path_from_db or os.path.normpath(path_candidate) != os.path.normpath(gallery_folder_path_from_db)):
                path_candidate = f"{expected_folder_full_path}_{counter}"
                counter += 1
            final_gallery_folder_path = path_candidate

            if gallery_folder_path_from_db and os.path.isdir(gallery_folder_path_from_db) and os.path.normpath(gallery_folder_path_from_db) != os.path.normpath(final_gallery_folder_path):
                try:
                    os.rename(gallery_folder_path_from_db, final_gallery_folder_path)
                except OSError as e_rename:
                    logger.error(f"PSG_ERROR ({gallery_id_input}): Nie udało się zmienić nazwy folderu: {e_rename}. Używam starej ścieżki.")
                    final_gallery_folder_path = gallery_folder_path_from_db 
            
            if os.path.normpath(final_gallery_folder_path) != os.path.normpath(gallery_folder_path_from_db or ""):
                 db_manager.update_gallery(gallery_id_input, folder_path=final_gallery_folder_path)
        
        if not final_gallery_folder_path:
            final_gallery_folder_path = expected_folder_full_path
            if os.path.normpath(final_gallery_folder_path) != os.path.normpath(gallery_folder_path_from_db or ""):
                db_manager.update_gallery(gallery_id_input, folder_path=final_gallery_folder_path)

        os.makedirs(final_gallery_folder_path, exist_ok=True)
        logger.info(f"PSG ({gallery_id_input}): Folder galerii ustawiony na: {final_gallery_folder_path}")

        # --- Krok 5: Pobieranie plików ---
        gallery_status_for_download_check = gallery_entry_db.get("status")
        statuses_preventing_download_strict = ['pending_production_ai', 'pending_test_ai', 'pending_initial_fetch_prod_ai', 'pending_initial_fetch_test_ai']
        
        should_download_files = True
        if gallery_status_for_download_check in statuses_preventing_download_strict:
            should_download_files = False
        elif gallery_status_for_download_check in ['completed', 'completed_with_tolerance']:
            is_forced_download_task = task_payload_for_triggers and task_payload_for_triggers.get('force_download', False)
            if not is_forced_download_task:
                should_download_files = False

        if should_download_files:
            prefetched_urls_for_download = None
            if collected_gallery_image_links_ref is not None and gallery_id_input in collected_gallery_image_links_ref:
                prefetched_urls_for_download = collected_gallery_image_links_ref.pop(gallery_id_input) 
            else: 
                if not page_already_loaded_this_call and not driver_utils.is_url_loaded(driver, gallery_url):
                     driver_utils.safe_driver_get(driver, gallery_url, shutdown_flag_func=shutdown_flag_func)
                     page_already_loaded_this_call = True
                image_link_elements_for_download = driver_utils.scroll_until_timeout(
                    driver, 'div.photo-item a[href]',
                    expected_count=gallery_entry_db.get('expected_count'),
                    gallery_id=gallery_id_input, model_name=model_name_from_db,
                    gallery_title=title_for_reporting,
                    initial_downloaded_count=gallery_entry_db.get('downloaded_count', 0),
                    current_expected_count_for_reporting=gallery_entry_db.get('expected_count'),
                    shutdown_flag_func=shutdown_flag_func
                )
                prefetched_urls_for_download = [el.get_attribute('href') for el in image_link_elements_for_download if el.get_attribute('href')]
                new_total_images_on_page = len(prefetched_urls_for_download)
                current_expected_db_val = gallery_entry_db.get('expected_count')
                if current_expected_db_val is None or new_total_images_on_page > current_expected_db_val:
                    db_manager.update_gallery(gallery_id_input, expected_count=new_total_images_on_page)
                    gallery_entry_db = db_manager.get_gallery(gallery_id_input)
            
            if prefetched_urls_for_download is not None:
                download_counts = dm_download_gallery(
                    driver, gallery_url, final_gallery_folder_path, gallery_id_input, model_name_from_db,
                    shutdown_flag_func=shutdown_flag_func,
                    prefetched_image_urls=prefetched_urls_for_download
                )
                
                gallery_after_download = db_manager.get_gallery(gallery_id_input) 
                status_before_final_update = gallery_after_download.get('status')
                downloaded_final = download_counts.get('downloaded_count', gallery_after_download.get('downloaded_count',0))
                expected_final = download_counts.get('expected_count', gallery_after_download.get('expected_count'))

                new_status_based_on_download = status_before_final_update 
                can_update_status_from_download = status_before_final_update not in statuses_preventing_download_strict
                if can_update_status_from_download:
                    new_status_based_on_download = 'error' 
                    tolerance_cfg = config_handler.current_config.get('downloading', {}).get('incomplete_gallery_completion_tolerance', {})
                    tolerance = tolerance_cfg.get('value', 2)
                    if expected_final is not None:
                        if downloaded_final >= expected_final:
                            new_status_based_on_download = 'completed'
                        elif (expected_final - downloaded_final) <= tolerance and downloaded_final > 0 :
                            new_status_based_on_download = 'completed_with_tolerance'
                        elif downloaded_final > 0:
                            new_status_based_on_download = 'partially_downloaded'
                    elif downloaded_final > 0: 
                        new_status_based_on_download = 'downloaded_unknown_total'
                    
                    if new_status_based_on_download != status_before_final_update:
                        db_manager.update_gallery(gallery_id_input, status=new_status_based_on_download, downloaded_count=downloaded_final, expected_count=expected_final)
                    else: 
                        db_manager.update_gallery(gallery_id_input, downloaded_count=downloaded_final, expected_count=expected_final)
                else:
                     db_manager.update_gallery(gallery_id_input, downloaded_count=downloaded_final, expected_count=expected_final)
            else:
                logger.warning(f"PSG ({gallery_id_input}): Brak linków do pobrania. Nie wywołuję dm_download_gallery.")
        else: 
            logger.info(f"PSG ({gallery_id_input}): Pominięto pobieranie plików (status: {gallery_status_for_download_check}).")

        # --- Końcowa pauza ---
        final_gallery_entry_db = db_manager.get_gallery(gallery_id_input)
        title_for_reporting_final = final_gallery_entry_db.get("determined_title") or final_gallery_entry_db.get("source_page_title") or final_gallery_entry_db.get("original_title") or gallery_id_input
        reporting.update_current_status("Pauza po galerii...", model=model_name_from_db, gallery=title_for_reporting_final, gallery_id=gallery_id_input, is_processing=False)
        time.sleep(config_handler.current_config['pauses_and_rotation']['gallery_pause']['value'] * random.uniform(0.8, 1.2))
        return True

    except constants.RestartRequiredError:
        logger.warning(f"PSG ({gallery_id_input}): RestartRequiredError. Galeria: {title_for_reporting}")
        reporting.update_current_status("Restart wymagany", model=model_name_original, gallery=title_for_reporting, gallery_id=gallery_id_input, is_processing=False)
        raise
    except Exception as e_main_gallery:
        logger.exception(f"PSG_ERROR ({gallery_id_input}): Krytyczny błąd przetwarzania galerii '{title_for_reporting}': {e_main_gallery}")
        initial_data_fetched_val = gallery_entry_db.get('initial_data_fetched', False)
        db_manager.update_gallery(gallery_id_input, status='error', error_message=str(e_main_gallery)[:1000], initial_data_fetched=initial_data_fetched_val)
        reporting.update_current_status("Błąd galerii", model=model_name_original, gallery=title_for_reporting, gallery_id=gallery_id_input, is_processing=False)
        return False


def handle_priority_item(item, driver_instance=None, shutdown_flag_func=None, collected_gallery_image_links_ref=None):
    config_handler.load_config()
    item_type, payload = item.get("type"), item.get("payload")
    item_display_info = str(payload.get("id", str(payload))) if isinstance(payload, dict) else str(payload)
    if not item_type or payload is None:
        logger.warning(f"Nieprawidłowy element priorytetowy: {item}. Usuwam z kolejki.")
        return True 

    logger.info(f"Przetwarzanie priorytetu: Typ='{item_type}', Dane='{item_display_info}'")
    
    driver_hpi = None 
    created_driver_in_hpi = False 
    rre_occurred_hpi = False

    try:
        if item_type == "re_analyze_gallery" or item_type == "re_analyze_gallery_test":
            logger.info(f"HPI ({item_display_info}): Zadanie typu '{item_type}'. Deleguję do AI workera przez zmianę statusu.")
            gallery_id = payload.get("id")
            if gallery_id:
                gallery_db_data = db_manager.get_gallery(gallery_id)
                if gallery_db_data:
                    is_test = item_type == "re_analyze_gallery_test"
                    new_status_target = 'pending_test_ai' if is_test else 'pending_production_ai'
                    
                    update_fields = {'status': new_status_target}
                    if is_test: update_fields['test_ai_title'] = None
                    else: update_fields['determined_title'] = None 

                    if not gallery_db_data.get('initial_data_fetched'):
                        logger.info(f"HPI ({gallery_id}): Zadanie '{item_type}' dla galerii bez danych inicjalnych. Ustawiam status na '{'pending_initial_fetch_test_ai' if is_test else 'pending_initial_fetch_prod_ai'}'.")
                        update_fields['status'] = 'pending_initial_fetch_test_ai' if is_test else 'pending_initial_fetch_prod_ai'
                        if 'task_payload_for_triggers' not in payload: payload['task_payload_for_triggers'] = {}
                        payload['task_payload_for_triggers']['trigger_action_after_fetch'] = 'test_ai' if is_test else 'production_ai'
                        payload['fetch_mode'] = 'initial_data_only'
                        item_type = 'gallery'
                        logger.warning(f"HPI ({gallery_id}): Zmieniono typ zadania na 'gallery' z fetch_mode='initial_data_only'.")
                    else:
                         logger.info(f"HPI ({gallery_id}): Galeria ma dane inicjalne. Ustawiam status na '{new_status_target}' dla workera AI.")
                    
                    db_manager.update_gallery(gallery_id, **update_fields)
                else:
                    logger.error(f"HPI ({gallery_id}): Nie znaleziono galerii dla zadania '{item_type}'.")
            return True

        if driver_instance and driver_utils.is_driver_responsive(driver_instance):
            driver_hpi = driver_instance
        elif item_type in ["gallery", "scan_model", "scan_model_refresh_only"]:
            driver_hpi = driver_utils.create_driver_with_retry(shutdown_flag_func=shutdown_flag_func)
            created_driver_in_hpi = True
        
        if not driver_hpi and item_type in ["gallery", "scan_model", "scan_model_refresh_only"]:
             logger.error(f"HPI Error ({item_display_info}): Nie udało się uzyskać drivera dla {item_type}. Pomijam.")
             return True 

        if item_type == "scan_model" or item_type == "scan_model_refresh_only":
            model_name_to_scan = str(payload)
            status_msg = "Priorytet: Odświeżanie modelu" if item_type == "scan_model_refresh_only" else "Priorytet: Skanowanie modelu"
            reporting.update_current_status(status_msg, model=model_name_to_scan, is_processing=True)
            _scan_new_model_page(driver_hpi, model_name_to_scan, shutdown_flag_func=shutdown_flag_func)
            reporting.update_current_status(f"Zakończono {status_msg} dla {model_name_to_scan}", model=model_name_to_scan, is_processing=False)

        elif item_type == "gallery":
            if not isinstance(payload, dict): logger.error(f"Nieprawidłowe 'payload' dla 'gallery': {payload}"); return True
            gallery_id, model_name = payload.get("id"), payload.get("model_name")
            gallery_url_from_payload = payload.get("url")
            fetch_mode_prio = payload.get("fetch_mode", "full") 
            
            if not gallery_id or not model_name :
                logger.error(f"HPI Error ({item_display_info}): Brak ID galerii/modelki w payload: {payload}"); return True

            gallery_db = db_manager.get_gallery(gallery_id)
            if not gallery_db: logger.error(f"HPI Error ({item_display_info}): Brak galerii {gallery_id} w DB."); return True

            url_to_process = gallery_url_from_payload if gallery_url_from_payload else gallery_db.get('url')
            if not url_to_process:
                 logger.error(f"HPI Error ({item_display_info}): Brak URL do przetworzenia dla galerii {gallery_id}"); return True

            title_rep = gallery_db.get("determined_title") or gallery_db.get("original_title") or gallery_id
            status_msg_suffix = f" (tryb: {fetch_mode_prio})"
            if fetch_mode_prio == "initial_data_only" and payload.get("trigger_action_after_fetch"):
                 status_msg_suffix += f" (trigger: {payload.get('trigger_action_after_fetch')})"
            
            reporting.update_current_status(f"Priorytet: Przetwarzanie galerii{status_msg_suffix}", gallery_id=gallery_id, model=model_name, gallery=title_rep, is_processing=True)
            
            process_single_gallery(driver_hpi, model_name, url_to_process, gallery_id,
                                   fetch_only_initial_data=(fetch_mode_prio == "initial_data_only"),
                                   task_payload_for_triggers=payload, 
                                   shutdown_flag_func=shutdown_flag_func,
                                   collected_gallery_image_links_ref=collected_gallery_image_links_ref
                                   )

            reporting.update_current_status(f"Zakończono priorytet: {title_rep}", model=model_name, gallery_id=gallery_id, gallery=title_rep, is_processing=False)
        else:
            logger.warning(f"HPI ({item_display_info}): Nieznany typ elementu priorytetowego: {item_type}")
        return True

    except constants.RestartRequiredError as rre:
        rre_occurred_hpi = True
        logger.warning(f"RRE w HPI ({item_display_info}): {rre}.")
        if item: db_manager.add_to_priority_queue(item.get("type"), item.get("payload"), add_to_front=True)
        raise
    except Exception as e:
        logger.exception(f"HPI_ERROR ({item_display_info}): Krytyczny błąd HPI: {e}")
        reporting.update_current_status(f"Błąd krytyczny prio: {item_type}", is_processing=False)
        return True 
    finally:
        if driver_hpi and created_driver_in_hpi and not rre_occurred_hpi:
            try:
                driver_hpi.quit()
            except Exception as e_quit:
                logger.warning(f"HPI ({item_display_info}): Błąd podczas zamykania drivera: {e_quit}")
        
        if not _is_shutdown_requested_processing(shutdown_flag_func) and not rre_occurred_hpi:
            if not db_manager.get_priority_queue(): 
                current_op_state_from_db = db_manager.get_app_state('script_state') or {}
                current_op_name_from_db = current_op_state_from_db.get("current_operation", {}).get("name")
                if not current_op_name_from_db: 
                     reporting.update_current_status("Oczekiwanie...", is_processing=False)

def handle_process_models(start_model_index=0, check_mode="all_or_incomplete", 
                          shutdown_flag_func=None, collected_gallery_image_links_ref=None):
    models_db = db_manager.execute_query("SELECT model_name FROM models ORDER BY model_name ASC", fetch_all=True)
    all_model_names = [row['model_name'] for row in models_db] if models_db else []

    if not all_model_names: 
        logger.info("Brak modelek w DB.")
        current_state = db_manager.get_app_state('script_state') or {}
        current_state["current_operation"] = {"name": None, "params": {}}
        db_manager.update_app_state('script_state', current_state)
        return
    
    models_to_process = all_model_names
    if 0 < start_model_index < len(all_model_names): models_to_process = all_model_names[start_model_index:]
    elif start_model_index >= len(all_model_names) and all_model_names: 
        logger.info("Wszystkie modelki przetworzone.")
        current_state = db_manager.get_app_state('script_state') or {}
        current_state["last_model_index_processed"] = -1
        current_state["current_operation"] = {"name": None, "params": {}}
        db_manager.update_app_state('script_state', current_state)
        reporting.update_current_status("Oczekiwanie...", is_processing=False)
        return

    driver, galleries_processed_since_vpn = None, 0
    config_handler.load_config()
    vpn_cfg = config_handler.current_config['pauses_and_rotation']
    vpn_threshold = random.randint(vpn_cfg['GALLERY_PAUSE_THRESHOLD_MIN']['value'], vpn_cfg['GALLERY_PAUSE_THRESHOLD_MAX']['value'])
    operation_should_stop, last_error = False, None
    try:
        driver = driver_utils.create_driver_with_retry(shutdown_flag_func=shutdown_flag_func)

        for model_idx, model_name in enumerate(models_to_process): 
            current_global_idx = all_model_names.index(model_name) 
            current_state_loop = db_manager.get_app_state('script_state') or {}
            current_state_loop["last_model_index_processed"] = current_global_idx
            db_manager.update_app_state('script_state', current_state_loop)

            if _is_shutdown_requested_processing(shutdown_flag_func) or operation_should_stop: break
            if config_handler.load_config(): logger.info("HPM: Konfiguracja przeładowana.")

            priority_processed_count = 0
            while True:
                if _is_shutdown_requested_processing(shutdown_flag_func): operation_should_stop = True; break
                priority_q = db_manager.get_priority_queue()
                if not priority_q or priority_processed_count >= 5: break
                
                priority_item = priority_q.pop(0)
                logger.info(f"HPM: Wyjęto z kolejki priorytetowej: {priority_item.get('type')} dla {priority_item.get('payload',{}).get('id', priority_item.get('payload'))}")
                
                try:
                    success_prio = handle_priority_item(
                        priority_item, 
                        driver_instance=driver, 
                        shutdown_flag_func=shutdown_flag_func,
                        collected_gallery_image_links_ref=collected_gallery_image_links_ref
                    )
                    if success_prio:
                        db_manager.save_priority_queue(priority_q) 
                    else: 
                        priority_item_payload = priority_item.get("payload", {})
                        logger.warning(f"HPM: Zadanie priorytetowe nie powiodło się. Przenoszę na koniec kolejki.")
                        db_manager.add_to_priority_queue(priority_item.get("type"), priority_item_payload, add_to_front=False)
                except constants.RestartRequiredError as rre_p:
                    if not driver_utils.is_driver_responsive(driver): driver = driver_utils.create_driver_with_retry(shutdown_flag_func=shutdown_flag_func)
                    raise rre_p 
                except Exception as e_p:
                    logger.exception(f"HPM: Nieobsłużony błąd w zadaniu priorytetowym: {e_p}")
                    if not driver_utils.is_driver_responsive(driver): driver = driver_utils.create_driver_with_retry(shutdown_flag_func=shutdown_flag_func) 
                priority_processed_count += 1
            
            if operation_should_stop: break 

            logger.info(f"=== PRZETWARZANIE MODELKI: {model_name} ({current_global_idx + 1}/{len(all_model_names)}) ===")
            reporting.update_current_status(f"Przetwarzanie ({check_mode})", model=model_name, is_processing=True)
            model_id_db = db_manager.get_or_create_model(model_name) 
            if not model_id_db: logger.warning(f"HPM: Nie udało się uzyskać ID dla modelki {model_name}. Pomijam."); continue
            
            model_folder_sanitized = utils.sanitize_foldername(model_name) 
            model_data_dir_path = os.path.join(constants.BASE_DATA_DIR, model_folder_sanitized)
            os.makedirs(model_data_dir_path, exist_ok=True)

            galleries_exist_for_model = bool(db_manager.execute_query("SELECT 1 FROM galleries WHERE model_id = %s LIMIT 1", (model_id_db,), fetch_one=True))
            if check_mode == "only_new_or_count_changed" or (check_mode == "all_or_incomplete" and not galleries_exist_for_model):
                try:
                    logger.info(f"HPM: Skanuję stronę modelki {model_name} (tryb: {check_mode})")
                    _scan_new_model_page(driver, model_name, shutdown_flag_func=shutdown_flag_func)
                except constants.RestartRequiredError: raise 
                except Exception as e_scan: logger.error(f"HPM Error: Błąd skanowania {model_name}: {e_scan}", exc_info=True); last_error = e_scan; continue
            
            galleries_for_model_processing = db_manager.get_model_galleries_for_processing(model_id_db, check_mode)
            logger.info(f"HPM: Znaleziono {len(galleries_for_model_processing)} galerii dla {model_name} w trybie '{check_mode}'.")
            
            for gal_data_item in galleries_for_model_processing:
                if _is_shutdown_requested_processing(shutdown_flag_func) or db_manager.get_priority_queue(): 
                    operation_should_stop = True; break
                
                try:
                    title_for_log = gal_data_item.get('determined_title') or gal_data_item.get('original_title') or gal_data_item['gallery_id']
                    logger.info(f"  HPM: Przetwarzanie galerii: {title_for_log} (ID: {gal_data_item['gallery_id']})")
                    
                    process_single_gallery(
                        driver, model_name, gal_data_item['url'], gal_data_item['gallery_id'],
                        fetch_only_initial_data=False,
                        task_payload_for_triggers=None,
                        shutdown_flag_func=shutdown_flag_func,
                        collected_gallery_image_links_ref=collected_gallery_image_links_ref
                    )
                    galleries_processed_since_vpn += 1
                    if galleries_processed_since_vpn >= vpn_threshold:
                        current_state_vpn = db_manager.get_app_state('script_state') or {}
                        current_state_vpn["last_model_index_processed"] = current_global_idx
                        db_manager.update_app_state('script_state', current_state_vpn)
                        raise constants.RestartRequiredError("Osiągnięto próg rotacji VPN")
                except constants.RestartRequiredError: raise 
                except Exception as e_gal: 
                    logger.exception(f"HPM Error: Błąd podczas przetwarzania galerii ID {gal_data_item['gallery_id']}: {e_gal}")
                    last_error = e_gal 
                
                if _is_shutdown_requested_processing(shutdown_flag_func): break 
            
            if operation_should_stop: 
                current_state_stop = db_manager.get_app_state('script_state') or {}
                current_state_stop["last_model_index_processed"] = current_global_idx
                db_manager.update_app_state('script_state', current_state_stop)
                break 
            logger.info(f"--- HPM: Zakończono model: {model_name} ---"); reporting.update_current_status(f"Zakończono model {model_name}", model=model_name, is_processing=False)
        
        if not _is_shutdown_requested_processing(shutdown_flag_func) and not operation_should_stop:
            logger.info(f"🎉 HPM: ZAKOŃCZONO WSZYSTKIE MODELKI ({check_mode}) 🎉")
            current_state_final = db_manager.get_app_state('script_state') or {}
            current_state_final["last_model_index_processed"] = -1
            current_state_final["current_operation"] = {"name": None, "params": {}}
            db_manager.update_app_state('script_state', current_state_final)
            reporting.update_current_status("Wszystkie modelki przetworzone. Oczekiwanie...", is_processing=False)

    except constants.RestartRequiredError as rre_hpm: 
        last_error = rre_hpm
        logger.warning(f"RRE w HPM: {rre_hpm}. Zapisano stan. Skrypt powinien zostać zrestartowany.")
        raise 
    except Exception as e_hpm: 
        last_error = e_hpm
        logger.exception(f"HPM Error: Krytyczny błąd HPM: {e_hpm}")
        current_state_err = db_manager.get_app_state('script_state') or {}
        current_state_err["current_operation"] = {"name": None, "params": {}}
        db_manager.update_app_state('script_state', current_state_err)
    finally:
        if driver:
            try: driver.quit()
            except Exception: pass
        if not _is_shutdown_requested_processing(shutdown_flag_func) and not isinstance(last_error, constants.RestartRequiredError):
            current_op_state_from_db_final = db_manager.get_app_state('script_state') or {}
            current_op_name_from_db_final = current_op_state_from_db_final.get("current_operation", {}).get("name")
            if not current_op_name_from_db_final:
                 reporting.update_current_status("Przetwarzanie zakończone. Oczekiwanie...", is_processing=False)

def handle_fill_incomplete(shutdown_flag_func=None, collected_gallery_image_links_ref=None):
    reporting.update_current_status("Uzupełnianie niekompletnych galerii...", is_processing=True)
    current_state = db_manager.get_app_state('script_state') or {}
    current_state["current_operation"] = {"name": None, "params": {}} 
    db_manager.update_app_state('script_state', current_state)
    try:
        incomplete_galleries = db_manager.get_incomplete_galleries_db_for_queue()
        if not incomplete_galleries: 
            logger.info("HFI: Brak niekompletnych galerii.")
            reporting.update_current_status("Brak niekompletnych.", is_processing=False)
            return
        logger.info(f"HFI: Znaleziono {len(incomplete_galleries)} niekompletnych. Dodaję do kolejki...")
        added_count = 0
        for gal_info in incomplete_galleries:
            if _is_shutdown_requested_processing(shutdown_flag_func): break 
            item_data = {'id': gal_info['gallery_id'], 'model_name': gal_info['model_name'],
                         'title': gal_info.get('determined_title') or gal_info.get('original_title') or gal_info['gallery_id'],
                         'count': gal_info.get('expected_count'),
                         'url': gal_info.get('url'),
                         'fetch_mode': 'full',
                         'force_download': True 
                         }
            if db_manager.add_to_priority_queue('gallery', item_data, add_to_front=True): added_count += 1
        logger.info(f"HFI: Dodano {added_count} z {len(incomplete_galleries)} do kolejki.")
        reporting.update_current_status(f"Dodano {added_count} galerii do uzupełnienia.", is_processing=False)
    except Exception as e_hfi: 
        logger.exception(f"Krytyczny błąd HFI: {e_hfi}")
        reporting.update_current_status(f"Błąd HFI: {str(e_hfi)[:100]}", is_processing=False)
    finally:
        current_op_state_from_db_hfi = db_manager.get_app_state('script_state') or {}
        current_op_name_from_db_hfi = current_op_state_from_db_hfi.get("current_operation", {}).get("name")
        if not current_op_name_from_db_hfi and not _is_shutdown_requested_processing(shutdown_flag_func) :
             reporting.update_current_status("Oczekiwanie...", is_processing=False)