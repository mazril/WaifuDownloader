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

# Przywrócono funkcję, ale nie jest ona już wywoływana z głównej pętli przetwarzania.
# Pozostaje jako narzędzie, które może być wywołane w innych celach (np. z interfejsu, dla testów).
def _refresh_galleries_data_for_model(driver, model_name_original, shutdown_flag_func=None):
    logger.info(f"Rozpoczynam odświeżanie danych wewnątrz galerii dla modelki: {model_name_original} (FUNKCJA LEGACY)")
    model_id = db_manager.get_or_create_model(model_name_original)
    if not model_id:
        logger.error(f"Nie udało się uzyskać ID dla modelki {model_name_original}. Przerywam odświeżanie.")
        return

    galleries_to_check = db_manager.get_model_galleries(model_id)
    if not galleries_to_check:
        logger.info(f"Brak galerii w bazie danych dla modelki {model_name_original}. Nic do zrobienia.")
        return
        
    logger.info(f"Znaleziono {len(galleries_to_check)} galerii dla {model_name_original}. Sprawdzam, które wymagają pobrania danych...")

    for i, gallery in enumerate(galleries_to_check):
        if _is_shutdown_requested_processing(shutdown_flag_func):
            logger.info("Przerwano odświeżanie danych galerii z powodu żądania zamknięcia.")
            break

        gallery_id = gallery.get('gallery_id')
        if gallery.get('initial_data_fetched'):
            logger.debug(f"Pomijam galerię {gallery_id}, ponieważ ma już pobrane dane inicjalne (initial_data_fetched=True).")
            continue

        gallery_url = gallery.get('url')
        if not gallery_url:
            logger.warning(f"Pomijam galerię {gallery_id}, ponieważ nie ma zapisanego URL.")
            continue
            
        logger.info(f"({i+1}/{len(galleries_to_check)}) Przetwarzam galerię: {gallery_id} (URL: {gallery_url})")
        reporting.update_current_status(
            f"Odświeżanie opisu {i+1}/{len(galleries_to_check)}",
            model=model_name_original, gallery=gallery.get('original_title') or gallery_id,
            gallery_id=gallery_id, is_processing=True
        )

        try:
            driver_utils.safe_driver_get(driver, gallery_url, shutdown_flag_func=shutdown_flag_func)
            
            page_derived_title = _get_gallery_page_title_candidate(driver)
            cosplay_tags, fandom_tags = _extract_cosplay_fandom_tags(driver)
            description = _get_gallery_description(driver)

            updates = {
                'initial_data_fetched': True,
                'last_processed_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            if page_derived_title:
                updates['source_page_title'] = page_derived_title
            if description:
                updates['gallery_description'] = description
            if cosplay_tags or fandom_tags:
                updates['tags_json'] = json.dumps({"cosplay": cosplay_tags, "fandom": fandom_tags}, ensure_ascii=False)
            
            db_manager.update_gallery(gallery_id, **updates)
            logger.info(f"  Sukces: Zaktualizowano dane dla galerii {gallery_id}.")
            
            time.sleep(random.uniform(1.0, 2.5))

        except constants.RestartRequiredError:
            raise
        except Exception as e:
            logger.error(f"  Błąd podczas odświeżania danych dla galerii {gallery_id}: {e}", exc_info=True)
            db_manager.update_gallery(gallery_id, status='error', error_message=f"Refresh data error: {str(e)[:200]}")
            
    logger.info(f"Zakończono odświeżanie danych wewnątrz galerii dla {model_name_original}.")

def process_single_gallery(driver, model_name_original, gallery_url, gallery_id_input,
                           shutdown_flag_func=None):
    """
    Przetwarza pojedynczą galerię: pobiera dane, linki, zleca AI, czeka na tytuł, pobiera pliki.

    Opis modyfikacji:
    - Funkcja ta jest teraz jedynym punktem wejścia do przetwarzania galerii.
    - Wewnętrznie sprawdza, czy `initial_data_fetched` jest fałszem i jeśli tak,
      pobiera dane (opis, tagi) przed przejściem do kolejnych kroków.
    - Logika oczekiwania na tytuł AI i pobierania plików pozostaje bez zmian.

    Wpływ na inne funkcje:
    - Zastępuje całkowicie potrzebę istnienia funkcji `_refresh_galleries_data_for_model`,
      unifikując logikę przetwarzania i rozwiązując problem "grazera".
    """
    logger.info(f"PSG_START ({gallery_id_input}): Rozpoczynam przetwarzanie.")
    config_handler.load_config()
    gallery_entry_db = db_manager.get_gallery(gallery_id_input)
    
    if not gallery_entry_db:
        logger.error(f"PSG_ERROR ({gallery_id_input}): Nie udało się pobrać danych galerii z DB! Pomijam.")
        return False

    if gallery_entry_db.get('is_disabled'):
        logger.info(f"PSG ({gallery_id_input}): Galeria jest oznaczona jako wyłączona. Pomijam.")
        return True

    model_name_from_db = gallery_entry_db.get('model_name', model_name_original)
    sanitized_model_name = gallery_entry_db.get('sanitized_name') or utils.sanitize_foldername(model_name_from_db)
    title_for_reporting = gallery_entry_db.get("determined_title") or gallery_entry_db.get("source_page_title") or gallery_entry_db.get("original_title") or gallery_id_input
    
    page_already_loaded_this_call = False

    try:
        # Krok 1: Pobranie danych inicjalnych (opis, tagi), jeśli ich brakuje.
        if not gallery_entry_db.get('initial_data_fetched'):
            logger.info(f"PSG ({gallery_id_input}): Wymagane pobranie danych inicjalnych (opis, tagi).")
            reporting.update_current_status(f"Pobieranie opisu...", model=model_name_from_db, gallery=title_for_reporting, gallery_id=gallery_id_input, is_processing=True)
            driver_utils.safe_driver_get(driver, gallery_url, shutdown_flag_func=shutdown_flag_func)
            page_already_loaded_this_call = True

            page_derived_title_candidate = _get_gallery_page_title_candidate(driver)
            cosplay_tags_list, fandom_tags_list = _extract_cosplay_fandom_tags(driver)
            gallery_description_text = _get_gallery_description(driver)
            
            updates = {'initial_data_fetched': True, 'last_processed_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')}
            if page_derived_title_candidate: updates['source_page_title'] = page_derived_title_candidate
            if gallery_description_text: updates['gallery_description'] = gallery_description_text
            if cosplay_tags_list or fandom_tags_list: updates['tags_json'] = json.dumps({"cosplay": cosplay_tags_list, "fandom": fandom_tags_list})
            
            db_manager.update_gallery(gallery_id_input, **updates)
            gallery_entry_db = db_manager.get_gallery(gallery_id_input) # Odśwież dane po aktualizacji
        
        # Krok 2: Zlecenie zadania dla AI, jeśli brakuje tytułu
        if not gallery_entry_db.get('determined_title') and gallery_entry_db.get('status') != 'pending_production_ai':
            logger.info(f"PSG ({gallery_id_input}): Brak 'determined_title'. Ustawiam status 'pending_production_ai'.")
            db_manager.update_gallery(gallery_id_input, status='pending_production_ai')
            gallery_entry_db = db_manager.get_gallery(gallery_id_input) # Odśwież
        
        # Krok 3: Zbieranie linków, jeśli ich brakuje
        if not gallery_entry_db.get('links_collected'):
            logger.info(f"PSG ({gallery_id_input}): Wymagane zebranie linków do obrazów.")
            if not page_already_loaded_this_call:
                driver_utils.safe_driver_get(driver, gallery_url, shutdown_flag_func=shutdown_flag_func)
            
            image_link_elements = driver_utils.scroll_until_timeout(
                driver, 'div.photo-item a[href]', 
                expected_count=gallery_entry_db.get('expected_count'), 
                gallery_id=gallery_id_input, model_name=model_name_from_db, 
                gallery_title=title_for_reporting,
                shutdown_flag_func=shutdown_flag_func
            )
            hrefs = [el.get_attribute('href') for el in image_link_elements if el.get_attribute('href')]
            
            updates = {'image_links_json': json.dumps(hrefs), 'links_collected': True}
            if gallery_entry_db.get('expected_count') is None or len(hrefs) > gallery_entry_db.get('expected_count', 0):
                updates['expected_count'] = len(hrefs)
            
            db_manager.update_gallery(gallery_id_input, **updates)
            logger.info(f"PSG ({gallery_id_input}): Zebrano i zapisano w DB {len(hrefs)} linków.")
            gallery_entry_db = db_manager.get_gallery(gallery_id_input) # Odśwież

        # Krok 4: Sprawdzenie tytułu AI z ewentualnym oczekiwaniem
        title_is_ready = gallery_entry_db.get('determined_title')
        if not title_is_ready:
            wait_timeout = config_handler.current_config['pauses_and_rotation']['ai_title_wait_timeout']['value']
            logger.info(f"PSG ({gallery_id_input}): Tytuł od AI nie jest gotowy. Czekam {wait_timeout}s.")
            reporting.update_current_status(f"Czekanie na AI ({wait_timeout}s)...", model=model_name_from_db, gallery=title_for_reporting, gallery_id=gallery_id_input, is_processing=True)
            time.sleep(wait_timeout)
            
            logger.info(f"PSG ({gallery_id_input}): Ponowne sprawdzanie tytułu w DB po oczekiwaniu.")
            gallery_entry_db = db_manager.get_gallery(gallery_id_input) # Kluczowe odświeżenie
            title_is_ready = gallery_entry_db.get('determined_title')

        if not title_is_ready:
            logger.info(f"PSG ({gallery_id_input}): Tytuł nadal nie jest gotowy. Kończę cykl dla tej galerii.")
            return True # Kończymy, ale operacja się udała, przechodzimy do następnej

        # Krok 5: Przygotowanie folderu i pobieranie (tylko jeśli tytuł jest gotowy)
        title_for_folder_creation = gallery_entry_db.get("determined_title")
        sanitized_folder_base = utils.sanitize_foldername(title_for_folder_creation)
        model_base_data_dir = os.path.join(constants.BASE_DATA_DIR, sanitized_model_name)
        os.makedirs(model_base_data_dir, exist_ok=True)

        final_gallery_folder_path = os.path.join(model_base_data_dir, sanitized_folder_base)
        if os.path.exists(final_gallery_folder_path) and not gallery_entry_db.get('folder_path'):
            final_gallery_folder_path = f"{final_gallery_folder_path}_{gallery_id_input}"
        
        os.makedirs(final_gallery_folder_path, exist_ok=True)
        if final_gallery_folder_path != gallery_entry_db.get('folder_path'):
            db_manager.update_gallery(gallery_id_input, folder_path=final_gallery_folder_path)

        logger.info(f"PSG ({gallery_id_input}): Folder galerii ustawiony na: {final_gallery_folder_path}")
        image_links_to_download = json.loads(gallery_entry_db.get('image_links_json'))
        
        download_result = dm_download_gallery(
            driver, gallery_url, final_gallery_folder_path, gallery_id_input, model_name_from_db,
            shutdown_flag_func=shutdown_flag_func,
            prefetched_image_urls=image_links_to_download
        )
        
        # Krok 6: Aktualizacja statusu po pobieraniu
        if download_result.get('was_disabled'):
            logger.info(f"PSG ({gallery_id_input}): Galeria oznaczona do wyłączenia. Aktualizuję DB.")
            db_manager.update_gallery(gallery_id_input, is_disabled=True, status='disabled_bad_links')
            return True 

        gallery_after_download = db_manager.get_gallery(gallery_id_input)
        downloaded_final = download_result.get('downloaded_count', 0)
        expected_final = download_result.get('expected_count', gallery_after_download.get('expected_count'))
        
        new_status = 'error'
        tolerance_percent = config_handler.current_config['downloading']['completion_tolerance_percent']['value']
        
        if expected_final is not None:
            if downloaded_final >= expected_final and expected_final > 0:
                new_status = 'completed'
            elif expected_final == 0 and downloaded_final == 0:
                new_status = 'completed'
            elif expected_final > 0 and (downloaded_final / expected_final * 100) >= tolerance_percent:
                new_status = 'completed_with_tolerance'
            elif downloaded_final > 0:
                new_status = 'partially_downloaded'
        elif downloaded_final > 0:
            new_status = 'downloaded_unknown_total'

        db_manager.update_gallery(gallery_id_input, status=new_status, downloaded_count=downloaded_final, expected_count=expected_final)

        reporting.update_current_status("Pauza po galerii...", model=model_name_from_db, gallery=title_for_reporting, gallery_id=gallery_id_input, is_processing=False)
        time.sleep(config_handler.current_config['pauses_and_rotation']['gallery_pause']['value'] * random.uniform(0.8, 1.2))
        return True

    except constants.RestartRequiredError:
        logger.warning(f"PSG ({gallery_id_input}): RestartRequiredError. Galeria: {title_for_reporting}")
        reporting.update_current_status("Restart wymagany", model=model_name_original, gallery=title_for_reporting, gallery_id=gallery_id_input, is_processing=False)
        raise
    except Exception as e_main_gallery:
        logger.exception(f"PSG_ERROR ({gallery_id_input}): Krytyczny błąd przetwarzania galerii '{title_for_reporting}': {e_main_gallery}")
        db_manager.update_gallery(gallery_id_input, status='error', error_message=str(e_main_gallery)[:1000])
        reporting.update_current_status("Błąd galerii", model=model_name_original, gallery=title_for_reporting, gallery_id=gallery_id_input, is_processing=False)
        return False


def handle_priority_item(item, driver_instance=None, shutdown_flag_func=None):
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
        if item_type in ["gallery", "scan_model", "scan_model_refresh_only"]:
            if driver_instance and driver_utils.is_driver_responsive(driver_instance):
                driver_hpi = driver_instance
            else:
                driver_hpi = driver_utils.create_driver_with_retry(shutdown_flag_func=shutdown_flag_func)
                created_driver_in_hpi = True
        
            if not driver_hpi:
                 logger.error(f"HPI Error ({item_display_info}): Nie udało się uzyskać drivera dla {item_type}. Pomijam.")
                 return True 

        if item_type == "scan_model":
            model_name_to_scan = str(payload)
            status_msg = "Priorytet: Skanowanie i uzupełnianie modelu"
            reporting.update_current_status(status_msg, model=model_name_to_scan, is_processing=True)
            _scan_new_model_page(driver_hpi, model_name_to_scan, shutdown_flag_func=shutdown_flag_func)
            
            # Po skanie, od razu przetwarzamy znalezione galerie
            galleries_to_process = db_manager.get_model_galleries_for_processing(db_manager.get_or_create_model(model_name_to_scan), "all_or_incomplete")
            for gal in galleries_to_process:
                if _is_shutdown_requested_processing(shutdown_flag_func): break
                process_single_gallery(driver_hpi, model_name_to_scan, gal['url'], gal['gallery_id'], shutdown_flag_func=shutdown_flag_func)

            reporting.update_current_status(f"Zakończono {status_msg} dla {model_name_to_scan}", model=model_name_to_scan, is_processing=False)

        elif item_type == "scan_model_refresh_only":
            model_name_to_scan = str(payload)
            status_msg = "Priorytet: Odświeżanie opisów galerii modelu"
            reporting.update_current_status(status_msg, model=model_name_to_scan, is_processing=True)
            _refresh_galleries_data_for_model(driver_hpi, model_name_to_scan, shutdown_flag_func=shutdown_flag_func)
            reporting.update_current_status(f"Zakończono {status_msg} dla {model_name_to_scan}", model=model_name_to_scan, is_processing=False)

        elif item_type == "gallery":
            gallery_id, model_name = payload.get("id"), payload.get("model_name")
            gallery_url_from_payload = payload.get("url")
            process_single_gallery(driver_hpi, model_name, gallery_url_from_payload, gallery_id,
                                   shutdown_flag_func=shutdown_flag_func)
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
                          shutdown_flag_func=None):
    """
    Główna funkcja orkiestrująca przetwarzanie modeli i ich galerii.

    Opis modyfikacji:
    - Usunięto wywołanie `_refresh_galleries_data_for_model` z tej pętli.
    - Główny cykl pracy teraz polega na skanowaniu nowości (`_scan_new_model_page`),
      a następnie pobieraniu listy wszystkich galerii wymagających pracy i
      wywoływaniu dla każdej z nich uniwersalnej funkcji `process_single_gallery`.

    Wpływ na inne funkcje:
    - Upraszcza logikę i rozwiązuje problem "grazera", zapewniając, że
      każda galeria jest przetwarzana kompleksowo w jednym podejściu.
    """
    models_db = db_manager.execute_query("SELECT model_id, model_name FROM models ORDER BY model_name ASC", fetch_all=True)
    all_models = models_db if models_db else []

    if not all_models: 
        logger.info("Brak modelek w DB.")
        db_manager.update_app_state('script_state', {"current_operation": {"name": None, "params": {}}})
        return
    
    models_to_process = all_models
    all_model_names = [m['model_name'] for m in all_models]
    if 0 < start_model_index < len(all_models): models_to_process = all_models[start_model_index:]
    
    driver = None
    operation_should_stop, last_error = False, None
    try:
        driver = driver_utils.create_driver_with_retry(shutdown_flag_func=shutdown_flag_func)
        processed_galleries_this_run = set()

        for model_data in models_to_process: 
            model_name = model_data['model_name']
            model_id_db = model_data['model_id']
            current_global_idx = all_model_names.index(model_name) 
            
            db_manager.update_app_state('script_state', {"last_model_index_processed": current_global_idx})

            if _is_shutdown_requested_processing(shutdown_flag_func): break
            
            logger.info(f"=== PRZETWARZANIE MODELKI: {model_name} ({current_global_idx + 1}/{len(all_models)}) ===")
            reporting.update_current_status(f"Przetwarzanie ({check_mode})", model=model_name, is_processing=True)
            
            # Krok 1: Skanowanie strony modelki w poszukiwaniu nowych/zaktualizowanych galerii
            _scan_new_model_page(driver, model_name, shutdown_flag_func=shutdown_flag_func)
            
            # Krok 2: Pobranie listy WSZYSTKICH galerii dla modelu, które wymagają jakiejkolwiek pracy
            galleries_for_model_processing = db_manager.get_model_galleries_for_processing(model_id_db, check_mode)
            
            for gal_data_item in galleries_for_model_processing:
                if _is_shutdown_requested_processing(shutdown_flag_func): break
                
                if gal_data_item['gallery_id'] in processed_galleries_this_run: continue

                # Przetwarzamy galerię kompleksowo
                process_single_gallery(driver, model_name, gal_data_item['url'], gal_data_item['gallery_id'], shutdown_flag_func=shutdown_flag_func)
                processed_galleries_this_run.add(gal_data_item['gallery_id'])
                
                # Sprawdzenie "oportunistyczne", czy inne galerie stały się gotowe w międzyczasie
                ready_to_download = db_manager.get_ready_to_download_galleries_for_model(model_id_db)
                for ready_gal in ready_to_download:
                    if ready_gal['gallery_id'] not in processed_galleries_this_run:
                        logger.info(f"  HPM: Wykryto gotową do pobrania galerię '{ready_gal['gallery_id']}'. Przetwarzam teraz.")
                        process_single_gallery(driver, model_name, ready_gal['url'], ready_gal['gallery_id'], shutdown_flag_func=shutdown_flag_func)
                        processed_galleries_this_run.add(ready_gal['gallery_id'])

            # Końcowe sprawdzenie gotowych galerii dla modelu po zakończeniu głównej pętli
            logger.info(f"HPM: Końcowe sprawdzanie gotowych galerii dla '{model_name}'.")
            final_check = db_manager.get_ready_to_download_galleries_for_model(model_id_db)
            for ready_gal in final_check:
                 if ready_gal['gallery_id'] not in processed_galleries_this_run:
                    process_single_gallery(driver, model_name, ready_gal['url'], ready_gal['gallery_id'], shutdown_flag_func=shutdown_flag_func)
                    processed_galleries_this_run.add(ready_gal['gallery_id'])

            logger.info(f"--- HPM: Zakończono model: {model_name} ---")
            
    except constants.RestartRequiredError as rre_hpm: 
        last_error = rre_hpm
        logger.warning(f"RRE w HPM: {rre_hpm}. Zapisano stan. Skrypt powinien zostać zrestartowany.")
        raise 
    except Exception as e_hpm: 
        last_error = e_hpm
        logger.exception(f"HPM Error: Krytyczny błąd HPM: {e_hpm}")
    finally:
        if driver:
            try: driver.quit()
            except Exception: pass