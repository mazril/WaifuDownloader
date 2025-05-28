# -*- coding: utf-8 -*-
import os
import time
import random
import traceback
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException, JavascriptException
from selenium.webdriver.support.ui import WebDriverWait # <--- DODANO
from selenium.webdriver.support import expected_conditions as EC # <--- DODANO
import logging

import constants
import config_handler
import utils
import data_manager 
import db_manager 
import driver_utils
import services
import reporting
import main 

logger = logging.getLogger(__name__)

def _scan_new_model_page(driver, model_name_original):
    """Skanuje stronę modelki, aby znaleźć linki do galerii, ich opisy i liczbę zdjęć."""
    logger.info(f"Rozpoczynam skanowanie strony dla modelki: {model_name_original}")
    model_id = db_manager.get_or_create_model(model_name_original) 
    if not model_id:
        logger.error(f"Nie udało się uzyskać/stworzyć ID dla modelki {model_name_original}. Pomijam skanowanie.")
        return []
        
    sanitized_model_name_for_url = utils.sanitize_foldername(model_name_original).lower().replace('_', '-')
    model_url = f"{constants.BASE_URL_SITE}/model/{sanitized_model_name_for_url}"

    try:
        driver_utils.safe_driver_get(driver, model_url)
        logger.info(f"Strona modelki '{model_name_original}' ({model_url}) załadowana.")

        gallery_link_selector = "a[href*='/gallery/'][class*='text-white']"
        logger.info(f"Rozpoczynam scrollowanie strony modelki '{model_name_original}' (selektor: '{gallery_link_selector}')...")

        link_elements = driver_utils.scroll_until_timeout(
            driver, gallery_link_selector, expected_count=None, allow_up_scroll=True,
            gallery_id=f"scan_{utils.sanitize_foldername(model_name_original)}",
            model_name=model_name_original, gallery_title="Skanowanie strony modelki"
        )

        scanned_galleries_data_for_db = []
        if not link_elements:
            logger.warning(f"Nie znaleziono żadnych elementów galerii dla '{model_name_original}' używając '{gallery_link_selector}'.")
            return []

        logger.info(f"Znaleziono {len(link_elements)} potencjalnych linków/tytułów. Przetwarzam...")
        processed_urls = set()

        for idx, link_el in enumerate(link_elements):
            gallery_url = "Nieznany"
            try:
                gallery_url = link_el.get_attribute('href')
                if not gallery_url or '/gallery/' not in gallery_url: continue
                if gallery_url in processed_urls: continue
                processed_urls.add(gallery_url)

                gallery_id_from_url = utils.get_gallery_id(gallery_url)
                if not gallery_id_from_url or gallery_id_from_url.startswith("error_"):
                    logger.warning(f"Nie udało się uzyskać poprawnego ID galerii z URL: {gallery_url}. Pomijam.")
                    continue

                original_title_from_scan = link_el.text.strip()
                if not original_title_from_scan: original_title_from_scan = gallery_id_from_url 

                expected_count_from_scan = None
                try:
                    grid_item_container = link_el.find_element(By.XPATH, "./ancestor::div[contains(@class, 'grid-item')]")
                    if grid_item_container:
                        count_span = grid_item_container.find_element(By.CSS_SELECTOR, "span.ms-1")
                        count_text = count_span.text.strip()
                        if count_text.isdigit(): expected_count_from_scan = int(count_text)
                except NoSuchElementException: pass 
                except Exception as e_count: logger.warning(f"Błąd ekstrakcji licznika dla '{original_title_from_scan}': {e_count}", exc_info=False)

                gallery_data = {
                    "gallery_id": gallery_id_from_url,
                    "model_id": model_id,
                    "url": gallery_url,
                    "original_title": original_title_from_scan,
                    "determined_title": None, 
                    "folder_path": None,      
                    "expected_count": expected_count_from_scan,
                    "downloaded_count": 0,    
                    "status": "pending_check", 
                    "last_processed_timestamp": None,
                    "error_message": None
                }
                db_manager.update_gallery_smart(gallery_data, only_if_newer_scan_data=True)
                scanned_galleries_data_for_db.append(gallery_data) 


            except WebDriverException as wde: logger.warning(f"Błąd WebDrivera (może StaleElement) przy linku #{idx+1}: {wde}. Pomijam.")
            except Exception as e: logger.warning(f"Błąd przetwarzania linku #{idx+1} ({gallery_url}): {e}", exc_info=False)

        logger.info(f"Zakończono skanowanie dla '{model_name_original}'. Przetworzono/zaktualizowano {len(scanned_galleries_data_for_db)} galerii w DB.")
        return scanned_galleries_data_for_db 
    except constants.RestartRequiredError: raise
    except Exception as e: logger.exception(f"Krytyczny błąd skanowania strony modelki {model_name_original}: {e}"); return []


def _get_page_js_variable_title(driver, timeout=7): 
    """Próbuje pobrać wartość zmiennej JavaScript 'title' ze strony, czekając na jej dostępność."""
    logger.info(f"Próba pobrania zmiennej JS 'title' ze strony (timeout: {timeout}s)...")
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return typeof title !== 'undefined' && title !== null && String(title).trim().length > 0;")
        )
        
        page_js_title = driver.execute_script("return String(title);") 
        
        if page_js_title: 
            page_js_title_stripped = page_js_title.strip()
            if page_js_title_stripped: 
                logger.info(f"Pobrano tytuł ze zmiennej JS 'title': \"{page_js_title_stripped}\"")
                return page_js_title_stripped
            else:
                logger.warning(f"Zmienna JS 'title' była dostępna, ale po usunięciu białych znaków jest pusta. Oryginalna wartość: '{page_js_title}'")
        else:
             logger.warning(f"Zmienna JS 'title' była dostępna, ale zwróciła null lub pustą wartość po konwersji na string. ")
            
    except TimeoutException:
        logger.warning(f"Timeout ({timeout}s) oczekiwania na zdefiniowanie zmiennej JS 'title' lub jej niepustą wartość.")
    except JavascriptException as je:
        logger.warning(f"Błąd JavaScript podczas próby pobrania/sprawdzania zmiennej 'title': {je}")
    except Exception as e:
        logger.warning(f"Nieoczekiwany błąd podczas pobierania zmiennej JS 'title': {e}", exc_info=True)
    return None


def _extract_cosplay_fandom_tags(driver):
    """Ekstrahuje tagi cosplay i fandom ze strony."""
    cosplay_tags = []
    fandom_tags = []
    try:
        tag_elements = driver.find_elements(By.CSS_SELECTOR, "a.btn[href*='/cosplay/'], a.btn[href*='/fandom/']")
        if not tag_elements: 
             tag_elements = driver.find_elements(By.XPATH, "//center//a[contains(@class, 'btn') and (contains(@href, '/cosplay/') or contains(@href, '/fandom/'))]")

        for tag_el in tag_elements:
            href = tag_el.get_attribute('href')
            text = tag_el.text.strip()
            if href and text:
                if '/cosplay/' in href:
                    cosplay_tags.append(text)
                elif '/fandom/' in href:
                    fandom_tags.append(text)
        if cosplay_tags: logger.info(f"Znaleziono tagi cosplay: {list(set(cosplay_tags))}") # Loguj unikalne
        if fandom_tags: logger.info(f"Znaleziono tagi fandom: {list(set(fandom_tags))}")   # Loguj unikalne
    except Exception as e:
        logger.warning(f"Błąd podczas ekstrakcji tagów cosplay/fandom: {e}", exc_info=False)
    return list(set(cosplay_tags)), list(set(fandom_tags)) 


def process_single_gallery(driver, model_name_original, gallery_url, gallery_id_input):
    config_handler.load_config()
    model_id = db_manager.get_or_create_model(model_name_original)
    if not model_id:
        logger.error(f"Nie udało się uzyskać ID dla modelki {model_name_original}. Pomijam galerię {gallery_id_input}.")
        return False

    gallery_id = gallery_id_input
    gallery_entry_db = db_manager.get_gallery(gallery_id)

    if not gallery_entry_db:
        logger.error(f"Nie znaleziono galerii o ID {gallery_id} w bazie danych dla modelki {model_name_original}. Pomijam.")
        return False

    current_original_title_from_db = gallery_entry_db.get("original_title") or gallery_id
    title_for_reporting_initial = gallery_entry_db.get("determined_title") or current_original_title_from_db

    reporting.update_current_status(
        "Przygotowanie galerii...", model=model_name_original, gallery=title_for_reporting_initial,
        gallery_id=gallery_id, is_processing=True,
        downloaded_count=gallery_entry_db.get("downloaded_count", 0),
        expected_count=gallery_entry_db.get("expected_count")
    )

    try:
        driver_utils.safe_driver_get(driver, gallery_url)

        page_js_title = _get_page_js_variable_title(driver)
        logger.info(f"Dla galerii {gallery_id}, page_js_title: '{page_js_title}', original_title z DB (scan): '{current_original_title_from_db}'")

        best_raw_title_before_ai = current_original_title_from_db
        if page_js_title and page_js_title.strip():
            if page_js_title != current_original_title_from_db:
                logger.info(f"Aktualizuję original_title dla galerii {gallery_id} z '{current_original_title_from_db}' na JS_TITLE: \"{page_js_title}\"")
                db_manager.execute_query("UPDATE galleries SET original_title = %s WHERE gallery_id = %s", (page_js_title, gallery_id), commit=True)
                gallery_entry_db["original_title"] = page_js_title
            best_raw_title_before_ai = page_js_title
        else:
            logger.info(f"Nie udało się pobrać page_js_title lub jest pusty dla galerii {gallery_id}. Używam original_title z DB: '{current_original_title_from_db}'")

        cosplay_hints, fandom_hints = _extract_cosplay_fandom_tags(driver)
        positive_ai_hints = list(set(cosplay_hints + fandom_hints))

        text_for_ai = best_raw_title_before_ai
        ai_raw_title = ""
        determined_title_from_ai = ""
        current_determined_title_in_db = gallery_entry_db.get("determined_title")

        if services.initialize_ai_model():
            logger.info(f"Przekazuję do AI dla galerii {gallery_id}: \"{text_for_ai}\", neg: [\"{model_name_original}\"], hints: {positive_ai_hints}")
            ai_raw_title = services.extract_gallery_name_t5(
                text_for_ai,
                negative_prompts_list=[model_name_original],
                positive_hints_list=positive_ai_hints
            )
            temp_determined_title = services.post_process_ai_title(ai_raw_title)

            if temp_determined_title:
                determined_title_from_ai = temp_determined_title
                logger.info(f"AI ustaliło tytuł dla {gallery_id}: \"{determined_title_from_ai}\" (surowy: \"{ai_raw_title}\")")
                if determined_title_from_ai != current_determined_title_in_db:
                    db_manager.execute_query("UPDATE galleries SET determined_title = %s WHERE gallery_id = %s", (determined_title_from_ai, gallery_id), commit=True)
                    gallery_entry_db["determined_title"] = determined_title_from_ai
            else:
                logger.warning(f"AI nie zwróciło użytecznego tytułu dla galerii {gallery_id} z tekstu \"{text_for_ai}\". Surowa odpowiedź AI: \"{ai_raw_title}\".")
                if current_determined_title_in_db:
                    determined_title_from_ai = current_determined_title_in_db
                    logger.info(f"Używam poprzednio zapisanego determined_title: \"{determined_title_from_ai}\"")
                else:
                    determined_title_from_ai = None # Ustaw na None, jeśli nie ma nic
                    if gallery_entry_db.get("determined_title") is not None: # Tylko jeśli było coś, a teraz ma być NULL
                        db_manager.execute_query("UPDATE galleries SET determined_title = NULL WHERE gallery_id = %s", (gallery_id,), commit=True)
                    gallery_entry_db["determined_title"] = None
                    logger.info("Brak nowego i poprzedniego determined_title. Pozostaje NULL.")
        else:
            logger.warning("Model AI niedostępny, pomijam ustalanie determined_title przez AI.")
            determined_title_from_ai = current_determined_title_in_db

        title_for_folder_base = determined_title_from_ai if determined_title_from_ai else best_raw_title_before_ai
        if not title_for_folder_base: 
            title_for_folder_base = gallery_id
            logger.warning(f"Brak tytułu (AI i original) dla galerii {gallery_id}, używam ID jako bazy nazwy folderu.")

        sanitized_folder_base = utils.sanitize_foldername(title_for_folder_base)
        gallery_folder_name = f"{sanitized_folder_base}_{gallery_id}"
        
        model_data_dir = data_manager.get_model_data_dir(utils.sanitize_foldername(model_name_original))
        folder_path = os.path.join(model_data_dir, gallery_folder_name)
        
        if gallery_entry_db.get("folder_path") != folder_path:
            db_manager.execute_query("UPDATE galleries SET folder_path = %s WHERE gallery_id = %s", (folder_path, gallery_id), commit=True)
            gallery_entry_db["folder_path"] = folder_path
        
        os.makedirs(folder_path, exist_ok=True)
        logger.info(f"Folder galerii: {folder_path}")

        expected_count_from_db = gallery_entry_db.get("expected_count")
        final_expected_count = expected_count_from_db 

        should_check_page_count = (final_expected_count is None) or \
                                  (gallery_entry_db.get("status") not in ["completed", "completed_with_tolerance"])
        if should_check_page_count:
            logger.info(f"Sprawdzanie licznika na stronie galerii {gallery_id} (obecny w DB: {final_expected_count})...")
            try:
                count_el = driver.find_element(By.CSS_SELECTOR, "h1 > span.ms-1") 
                count_txt = count_el.text.strip()
                if count_txt.isdigit():
                    count_page = int(count_txt)
                    logger.info(f"Licznik ze strony galerii: {count_page}.")
                    if final_expected_count is None or count_page > final_expected_count:
                        final_expected_count = count_page
                        logger.info(f"Aktualizuję expected_count dla {gallery_id} na {final_expected_count} (z było {expected_count_from_db}).")
                        db_manager.execute_query("UPDATE galleries SET expected_count = %s WHERE gallery_id = %s", (final_expected_count, gallery_id), commit=True)
                        gallery_entry_db["expected_count"] = final_expected_count
                    elif count_page < final_expected_count:
                         logger.warning(f"Licznik ze strony ({count_page}) jest mniejszy niż znany w DB ({final_expected_count}). Pozostaję przy wartości z DB.")
                else:
                    logger.warning(f"Tekst licznika ze strony galerii ('{count_txt}') nie jest liczbą.")
            except NoSuchElementException:
                logger.warning(f"Brak elementu licznika ('h1 > span.ms-1') na stronie galerii {gallery_id}.")
            except Exception as e_count_page:
                logger.warning(f"Błąd podczas pobierania licznika ze strony galerii {gallery_id}: {e_count_page}", exc_info=False)
        
        title_for_reporting_final = determined_title_from_ai or best_raw_title_before_ai or gallery_id
        logger.info(f"Ostateczny expected_count dla galerii '{title_for_reporting_final}' (ID: {gallery_id}): {final_expected_count or 'Nadal nieznany'}")

        current_files_on_disk = set(os.listdir(folder_path)) if os.path.exists(folder_path) else set()
        final_dl_count_on_disk = len(current_files_on_disk)
        new_files_downloaded_this_session = 0

        if final_expected_count is not None and final_dl_count_on_disk >= final_expected_count:
            logger.info(f"Galeria '{title_for_reporting_final}' ({gallery_id}) już kompletna na dysku ({final_dl_count_on_disk}/{final_expected_count}). Pomijam pobieranie.")
            imgs_elements_to_download = []
        else:
            reporting.update_current_status(
                f"Przygotowanie do scrolla", model=model_name_original, gallery=title_for_reporting_final, 
                gallery_id=gallery_id, is_processing=True, 
                downloaded_count=final_dl_count_on_disk, 
                expected_count=final_expected_count
            )
            imgs_elements_to_download = driver_utils.scroll_until_timeout(
                driver, 'div.photo-item a[href]', 
                expected_count=final_expected_count, 
                allow_up_scroll=False, 
                gallery_id=gallery_id, 
                model_name=model_name_original, 
                gallery_title=title_for_reporting_final, 
                initial_downloaded_count=final_dl_count_on_disk,
                current_expected_count_for_reporting=final_expected_count
            )

        if imgs_elements_to_download:
            logger.info(f"Pobieram {len(imgs_elements_to_download)} linków dla '{title_for_reporting_final}'. Na dysku: {final_dl_count_on_disk}.")
            reporting.update_current_status(
                f"Pobieranie... ({final_dl_count_on_disk})", model=model_name_original, gallery=title_for_reporting_final,
                gallery_id=gallery_id, is_processing=True, downloaded_count=final_dl_count_on_disk,
                scan_session_found_count=len(imgs_elements_to_download), expected_count=final_expected_count
            )
            for el in imgs_elements_to_download:
                if main.shutdown_requested: logger.info(f"Przerwano pobieranie dla {gallery_id}."); break
                try: img_url = el.get_attribute('href')
                except Exception as e_href: logger.warning(f"Błąd pobierania href atrybutu: {e_href}", exc_info=False); continue
                if not img_url: continue
                img_filename = os.path.basename(utils.urlparse(img_url).path)
                if not img_filename: continue
                
                if img_filename not in current_files_on_disk:
                    if services.download_image(img_url, os.path.join(folder_path, img_filename)):
                        new_files_downloaded_this_session += 1
                        current_files_on_disk.add(img_filename) 
                        final_dl_count_on_disk = len(current_files_on_disk)
                        reporting.update_current_status(
                            f"Pobrano {new_files_downloaded_this_session} ({final_dl_count_on_disk})...", model=model_name_original,
                            gallery=title_for_reporting_final, gallery_id=gallery_id, is_processing=True,
                            downloaded_count=final_dl_count_on_disk, 
                            scan_session_found_count=len(imgs_elements_to_download), 
                            expected_count=final_expected_count
                        )
                time.sleep(0.01) 
        else:
            logger.info(f"Brak nowych elementów do pobrania dla '{title_for_reporting_final}' ({gallery_id}) lub galeria kompletna.")

        final_dl_count_on_disk = len(os.listdir(folder_path)) if os.path.exists(folder_path) else 0
        logger.info(f"Galeria '{title_for_reporting_final}': pobrano {new_files_downloaded_this_session} nowych plików w tej sesji. Łącznie na dysku: {final_dl_count_on_disk}. Oczekiwano: {final_expected_count or '?'}.")
        
        new_status = "pending_check"
        tolerance = config_handler.current_config['downloading']['incomplete_gallery_completion_tolerance']['value']
        if final_expected_count is not None:
            if final_dl_count_on_disk >= final_expected_count:
                new_status = "completed"
            elif (final_expected_count - final_dl_count_on_disk) <= tolerance and final_dl_count_on_disk > 0:
                new_status = "completed_with_tolerance"
            else:
                new_status = "partially_downloaded"
        elif final_dl_count_on_disk > 0: 
            new_status = "downloaded_unknown_total"
        
        logger.debug(f"Ustawiam status galerii '{title_for_reporting_final}' na: {new_status}")
        
        db_manager.execute_query(
            "UPDATE galleries SET downloaded_count = %s, status = %s, last_processed_timestamp = %s, error_message = NULL WHERE gallery_id = %s",
            (final_dl_count_on_disk, new_status, time.strftime("%Y-%m-%d %H:%M:%S"), gallery_id),
            commit=True
        )
        
        time.sleep(0.25)
        gallery_pause_duration = config_handler.current_config['pauses_and_rotation']['gallery_pause']['value']
        reporting.update_current_status(
            "Pauza po galerii", model=model_name_original, gallery=title_for_reporting_final, 
            gallery_id=gallery_id, is_processing=False, 
            downloaded_count=final_dl_count_on_disk, expected_count=final_expected_count
        )
        time.sleep(gallery_pause_duration * random.uniform(0.8, 1.2))
        return True

    except constants.RestartRequiredError:
        reporting.update_current_status("Restart wymagany", model=model_name_original, gallery=title_for_reporting_initial, gallery_id=gallery_id, is_processing=False)
        raise
    except Exception as e_main_gallery:
        logger.exception(f"Krytyczny błąd podczas przetwarzania galerii {gallery_id} ('{title_for_reporting_initial}'): {e_main_gallery}")
        db_manager.execute_query(
            "UPDATE galleries SET status = %s, error_message = %s, last_processed_timestamp = %s WHERE gallery_id = %s",
            ("error", str(e_main_gallery)[:1000], time.strftime("%Y-%m-%d %H:%M:%S"), gallery_id),
            commit=True
        )
        reporting.update_current_status("Błąd galerii", model=model_name_original, gallery=title_for_reporting_initial, gallery_id=gallery_id, is_processing=False)
        return False

# Reszta pliku processing.py (handle_priority_item, handle_process_models, handle_fill_incomplete)
# pozostaje taka sama jak w mojej poprzedniej odpowiedzi, gdzie te funkcje zostały już dostosowane
# do nowego sposobu wywoływania process_single_gallery i aktualizacji w DB.
# Jeśli chcesz, mogę je tutaj powtórzyć dla kompletności.
# Poniżej wklejam resztę pliku, zakładając, że poprzednie zmiany w tych funkcjach są już uwzględnione.

def handle_priority_item(item, driver_instance=None):
    # ... (kod z poprzedniej odpowiedzi, który poprawnie wywołuje process_single_gallery(driver, model_name, gallery_url, gallery_id)) ...
    config_handler.load_config()
    item_type = item.get("type")
    payload = item.get("data") 
    item_display_info = str(payload.get("id", str(payload))) if isinstance(payload, dict) else str(payload)
    
    if not item_type or payload is None: 
        logger.warning(f"Nieprawidłowy element priorytetowy: {item}. Pomijam.")
        return

    logger.info(f"Przetwarzanie elementu priorytetowego: Typ='{item_type}', Dane='{item_display_info}'")
    driver = None
    created_driver_here = False
    rre_occurred = False

    try:
        if item_type == "scan_model" or item_type == "scan_model_refresh_only":
            model_name_to_scan = str(payload) 
            is_refresh_only = item_type == "scan_model_refresh_only"
            status_msg = "Priorytet: Odświeżanie danych modelu" if is_refresh_only else "Priorytet: Skanowanie modelu"
            reporting.update_current_status(status_msg, model=model_name_to_scan, is_processing=True)
            
            if driver_instance and driver_utils.is_driver_responsive(driver_instance):
                driver = driver_instance
            else:
                driver = driver_utils.create_driver_with_retry()
                created_driver_here = True
            
            _scan_new_model_page(driver, model_name_to_scan) 
            
            logger.info(f"{status_msg} dla '{model_name_to_scan}' zakończone.")
            reporting.update_current_status(f"Zakończono {status_msg} dla {model_name_to_scan}", model=model_name_to_scan, is_processing=False)

        elif item_type == "gallery":
            if not isinstance(payload, dict): 
                logger.error(f"Nieprawidłowy format 'data' dla typu 'gallery' w kolejce: oczekiwano dict, jest {type(payload)}. Payload: {payload}"); return
            
            gallery_id_to_process = payload.get("id")
            model_name_for_gallery = payload.get("model_name")
            gallery_title_from_queue = payload.get("title", gallery_id_to_process) 
            
            if not gallery_id_to_process or not model_name_for_gallery:
                logger.error(f"Brak ID galerii lub nazwy modelki w danych priorytetowych dla galerii: {payload}. Pomijam."); return

            gallery_db_entry = db_manager.get_gallery(gallery_id_to_process)
            if not gallery_db_entry or not gallery_db_entry.get('url'):
                logger.error(f"Nie znaleziono URL dla galerii {gallery_id_to_process} (model: {model_name_for_gallery}) w bazie danych. Pomijam priorytet.")
                return

            gallery_url_to_process = gallery_db_entry['url']
            title_for_reporting_prio = gallery_db_entry.get("determined_title") or gallery_db_entry.get("original_title") or gallery_title_from_queue

            reporting.update_current_status(
                "Priorytet: Przetwarzanie galerii", gallery_id=gallery_id_to_process, 
                model=model_name_for_gallery, gallery=title_for_reporting_prio, is_processing=True
            )
            
            if driver_instance and driver_utils.is_driver_responsive(driver_instance):
                driver = driver_instance
            else:
                driver = driver_utils.create_driver_with_retry()
                created_driver_here = True
            
            services.initialize_ai_model() 
            
            process_single_gallery(driver, model_name_for_gallery, gallery_url_to_process, gallery_id_to_process)
            
            logger.info(f"Zakończono przetwarzanie priorytetowe galerii {gallery_id_to_process} dla modelki {model_name_for_gallery}.")
            reporting.update_current_status(
                f"Zakończono priorytet: {title_for_reporting_prio}", model=model_name_for_gallery, 
                gallery_id=gallery_id_to_process, gallery=title_for_reporting_prio, is_processing=False
            )
        else:
            logger.warning(f"Nieznany typ elementu w kolejce priorytetowej: {item_type}")

    except constants.RestartRequiredError as rre: 
        rre_occurred = True
        logger.warning(f"RestartRequiredError w handle_priority_item ({item_display_info}): {rre}.")
        if created_driver_here and driver:
            try: driver.quit(); logger.info("Zamknięto driver (HPI) po RRE.")
            except Exception as e_quit: logger.warning(f"Błąd quit drivera (HPI RRE): {e_quit}")
        raise 
    except Exception as e: 
        logger.exception(f"Krytyczny błąd podczas przetwarzania elementu priorytetowego {item_display_info}: {e}")
        reporting.update_current_status(f"Błąd krytyczny prio: {item_type} - {item_display_info}", is_processing=False)
    finally: 
        if driver and created_driver_here and not rre_occurred:
            logger.info(f"Zamykam driver (HPI, finally, no RRE) dla {item_display_info}")
            try: driver.quit()
            except Exception as e_quit_fin: logger.warning(f"Błąd quit drivera (HPI finally): {e_quit_fin}")
        is_exception_other_than_rre = 'e' in locals() and not isinstance(locals().get('e'), constants.RestartRequiredError)
        if not main.shutdown_requested and not rre_occurred and not is_exception_other_than_rre:
            current_operation_state = data_manager.load_script_state().get("current_operation", {})
            if not current_operation_state.get("name"): 
                 reporting.update_current_status("Oczekiwanie...", is_processing=False)


def handle_process_models(start_model_index=0, check_mode="all_or_incomplete"):
    all_model_names_from_db = data_manager.read_model_list() 
    if not all_model_names_from_db: 
        logger.info("Brak modelek w bazie danych do przetworzenia."); 
        data_manager.clear_active_operation()
        return

    models_to_process_in_run = all_model_names_from_db
    if start_model_index > 0 and start_model_index < len(all_model_names_from_db):
        logger.info(f"Wznawiam przetwarzanie modeli od indeksu: {start_model_index} ({all_model_names_from_db[start_model_index]})")
        models_to_process_in_run = all_model_names_from_db[start_model_index:]
    elif start_model_index >= len(all_model_names_from_db) and len(all_model_names_from_db) > 0 : 
        logger.info("Wszystkie modelki zostały już przetworzone w tej sesji (lub indeks poza zakresem).")
        # Pytanie o restart nie jest już potrzebne tutaj, bo menu główne to obsłuży
        data_manager.update_last_model_index(-1) # Oznacz jako zakończone
        data_manager.clear_active_operation()
        reporting.update_current_status("Oczekiwanie...", is_processing=False)
        return


    driver = None
    galleries_processed_since_last_vpn_rotation = 0
    last_processing_error = None
    config_handler.load_config() 
    vpn_rotation_config = config_handler.current_config['pauses_and_rotation']
    vpn_rotation_threshold = random.randint(
        vpn_rotation_config['GALLERY_PAUSE_THRESHOLD_MIN']['value'], 
        vpn_rotation_config['GALLERY_PAUSE_THRESHOLD_MAX']['value']
    )
    logger.info(f"Rozpoczynam handle_process_models. Tryb: {check_mode}. Próg VPN: {vpn_rotation_threshold} galerii.")
    operation_should_stop = False

    try:
        driver = driver_utils.create_driver_with_retry()
        services.initialize_ai_model()

        for model_idx_loop, model_name_original in enumerate(models_to_process_in_run):
            current_global_model_index = all_model_names_from_db.index(model_name_original) 
            data_manager.update_last_model_index(current_global_model_index) 

            if main.shutdown_requested or operation_should_stop: 
                logger.info("HPM: Otrzymano żądanie zatrzymania lub wystąpił błąd krytyczny."); break
            
            if config_handler.load_config(): logger.info("HPM: Konfiguracja przeładowana.")

            priority_batch_processed_count = 0
            while True:
                if main.shutdown_requested: operation_should_stop = True; break
                priority_queue = data_manager.load_priority_queue()
                if not priority_queue: break
                if priority_batch_processed_count >= 5: 
                    logger.info(f"HPM: Przetworzono {priority_batch_processed_count} elementów priorytetowych. Kontynuuję z modelem głównym.")
                    break
                logger.info(f"HPM: Znaleziono {len(priority_queue)} elementów w kolejce priorytetowej. Przetwarzam pierwszy...");
                priority_item = priority_queue.pop(0)
                data_manager.save_priority_queue(priority_queue) 
                try:
                    handle_priority_item(priority_item, driver_instance=driver)
                except constants.RestartRequiredError as rre_priority:
                    logger.warning(f"RestartRequiredError w zadaniu priorytetowym ({priority_item.get('type')}): {rre_priority}. Przekazuję dalej.")
                    if not driver_utils.is_driver_responsive(driver): driver = driver_utils.create_driver_with_retry()
                    raise rre_priority 
                except Exception as e_priority:
                    logger.exception(f"Nieobsłużony błąd w zadaniu priorytetowym ({priority_item.get('type')}): {e_priority}")
                    if not driver_utils.is_driver_responsive(driver):
                        logger.warning("Driver niereponsywny po błędzie w zadaniu priorytetowym. Odtwarzam.")
                        try: driver.quit() 
                        except: pass
                        driver = driver_utils.create_driver_with_retry()
                priority_batch_processed_count += 1
            if operation_should_stop: break


            logger.info(f"=== PRZETWARZANIE MODELKI: {model_name_original} ({current_global_model_index + 1}/{len(all_model_names_from_db)}) ===")
            reporting.update_current_status(f"Przetwarzanie modelu ({check_mode})", model=model_name_original, is_processing=True)
            
            model_id = db_manager.get_or_create_model(model_name_original) 
            if not model_id: 
                logger.error(f"Nie udało się uzyskać ID dla modelki {model_name_original} z DB. Pomijam."); continue

            os.makedirs(data_manager.get_model_data_dir(utils.sanitize_foldername(model_name_original)), exist_ok=True)

            galleries_exist_in_db = bool(db_manager.execute_query("SELECT 1 FROM galleries WHERE model_id = %s LIMIT 1", (model_id,), fetch_one=True))

            if check_mode == "only_new_or_count_changed" or \
               (check_mode == "all_or_incomplete" and not galleries_exist_in_db):
                logger.info(f"Skanowanie strony dla modelki {model_name_original} (tryb: {check_mode}, czy istnieją galerie w DB: {galleries_exist_in_db})...")
                try:
                    _scan_new_model_page(driver, model_name_original) 
                    if main.shutdown_requested: operation_should_stop = True; break
                except constants.RestartRequiredError: raise
                except Exception as e_scan_page:
                    logger.error(f"Błąd podczas skanowania strony modelki {model_name_original}: {e_scan_page}", exc_info=True)
                    last_processing_error = e_scan_page
                    if main.shutdown_requested: operation_should_stop = True; break
                    continue 
            
            galleries_to_process_db = db_manager.get_model_galleries_for_processing(model_id, check_mode)
            logger.info(f"Znaleziono {len(galleries_to_process_db)} galerii do przetworzenia dla {model_name_original} w trybie '{check_mode}'.")

            for gallery_db_data in galleries_to_process_db:
                if main.shutdown_requested: operation_should_stop = True; break
                if data_manager.load_priority_queue(): 
                    logger.info("HPM: Wykryto nowe elementy w kolejce priorytetowej. Przerywam przetwarzanie modelu.")
                    data_manager.update_last_model_index(current_global_model_index) 
                    return 

                try:
                    gallery_title_rep = gallery_db_data.get('determined_title') or gallery_db_data.get('original_title') or gallery_db_data.get('gallery_id')
                    logger.info(f"  Przetwarzanie galerii: {gallery_title_rep} (ID: {gallery_db_data['gallery_id']})")
                    
                    process_single_gallery(driver, model_name_original, gallery_db_data['url'], gallery_db_data['gallery_id'])
                    
                    galleries_processed_since_last_vpn_rotation += 1
                    if galleries_processed_since_last_vpn_rotation >= vpn_rotation_threshold:
                        logger.info(f"Osiągnięto próg VPN ({galleries_processed_since_last_vpn_rotation} galerii). Wymagany restart.")
                        data_manager.update_last_model_index(current_global_model_index)
                        raise constants.RestartRequiredError("Osiągnięto próg rotacji VPN")
                except constants.RestartRequiredError: raise 
                except Exception as e_gallery_proc:
                    logger.exception(f"Błąd podczas przetwarzania galerii ID {gallery_db_data['gallery_id']} dla modelki {model_name_original}: {e_gallery_proc}")
                    last_processing_error = e_gallery_proc
                
                if main.shutdown_requested: operation_should_stop = True; break
                time.sleep(0.25) 
            
            if operation_should_stop: break
            
            logger.info(f"--- Zakończono przetwarzanie modelu: {model_name_original} ---")
            reporting.update_current_status(f"Zakończono model {model_name_original}", model=model_name_original, is_processing=False)
            time.sleep(0.5) 

        if not main.shutdown_requested and not operation_should_stop:
            logger.info(f"🎉 ZAKOŃCZONO WSZYSTKIE MODELKI ({check_mode}) 🎉")
            data_manager.update_last_model_index(-1) 
            data_manager.clear_active_operation()
            
    except constants.RestartRequiredError as rre_hpm: 
        last_processing_error = rre_hpm
        logger.warning(f"RestartRequiredError w handle_process_models: {rre_hpm}.")
        raise 
    except Exception as e_hpm_main: 
        last_processing_error = e_hpm_main
        logger.exception(f"Krytyczny błąd w handle_process_models: {e_hpm_main}")
        data_manager.clear_active_operation() 
    finally: 
        if driver:
            logger.info("Zamykanie drivera (finally handle_process_models)...")
            try: driver.quit()
            except Exception as e_quit_hpm: logger.warning(f"Błąd podczas zamykania drivera w HPM: {e_quit_hpm}")
        is_rre_final = isinstance(last_processing_error, constants.RestartRequiredError)
        if not main.shutdown_requested and not is_rre_final: 
            current_operation_state = data_manager.load_script_state().get("current_operation",{})
            final_message = "Zakończono/Przerwano przetwarzanie modeli."
            if not current_operation_state.get("name"): 
                final_message = "Przetwarzanie modeli zakończone. Oczekiwanie..."
            reporting.update_current_status(final_message, is_processing=False)


def handle_fill_incomplete():
    reporting.update_current_status("Uzupełnianie niekompletnych galerii...", is_processing=True)
    data_manager.clear_active_operation() 
    
    try:
        incomplete_galleries_from_db = db_manager.get_incomplete_galleries_db_for_queue() 
        
        if not incomplete_galleries_from_db:
            logger.info("HFI: Brak niekompletnych galerii w bazie danych do dodania do kolejki.")
            reporting.update_current_status("Brak niekompletnych galerii.", is_processing=False)
            return

        logger.info(f"HFI: Znaleziono {len(incomplete_galleries_from_db)} niekompletnych galerii. Dodaję do kolejki priorytetowej...")
        added_to_queue = 0
        for gal_info in incomplete_galleries_from_db:
            item_data_for_queue = {
                'id': gal_info['gallery_id'],
                'model_name': gal_info['model_name'],
                'title': gal_info.get('determined_title') or gal_info.get('original_title') or gal_info['gallery_id'],
                'count': gal_info.get('expected_count') 
            }
            if data_manager.add_to_priority_queue('gallery', item_data_for_queue, prepend=True): 
                added_to_queue += 1
        
        logger.info(f"HFI: Dodano {added_to_queue} z {len(incomplete_galleries_from_db)} niekompletnych galerii do kolejki priorytetowej.")
        reporting.update_current_status(f"Dodano {added_to_queue} galerii do uzupełnienia do kolejki.", is_processing=False)

    except Exception as e_hfi: 
        logger.exception(f"Krytyczny błąd w handle_fill_incomplete: {e_hfi}")
        reporting.update_current_status(f"Błąd podczas uzupełniania niekompletnych: {str(e_hfi)[:100]}", is_processing=False)
    finally: 
        current_operation_state = data_manager.load_script_state().get("current_operation", {})
        if not current_operation_state.get("name"): 
             reporting.update_current_status("Oczekiwanie...", is_processing=False)