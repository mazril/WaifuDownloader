# -*- coding: utf-8 -*-
import os
import time
import random
import traceback
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, WebDriverException
import logging

import constants
import config_handler
import utils
import data_manager
import driver_utils
import services
import reporting
import main # Dla main.shutdown_requested

logger = logging.getLogger(__name__)

def _scan_new_model_page(driver, model_name_original):
    """Skanuje stronę modelki, aby znaleźć linki do galerii, ich opisy i liczbę zdjęć."""
    logger.info(f"Rozpoczynam skanowanie strony dla modelki: {model_name_original}")
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

        scanned_galleries = []
        if not link_elements:
            logger.error(f"Nie znaleziono żadnych elementów galerii dla '{model_name_original}' używając '{gallery_link_selector}'. Sprawdź selektor lub stronę.")
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

                title = link_el.text.strip()
                if not title: title = utils.get_gallery_id(gallery_url)

                count = None
                try:
                    grid_item_container = link_el.find_element(By.XPATH, "./ancestor::div[contains(@class, 'grid-item')]")
                    if grid_item_container:
                        count_span = grid_item_container.find_element(By.CSS_SELECTOR, "span.ms-1")
                        count_text = count_span.text.strip()
                        if count_text.isdigit(): count = int(count_text)
                        logger.debug(f"  Licznik dla '{title}': {count if count is not None else 'N/A'} (tekst: '{count_text}')")
                    else: logger.debug(f"  Brak kontenera 'grid-item' dla '{title}'.")
                except NoSuchElementException: logger.debug(f"  Brak licznika (span.ms-1) dla '{title}' (NSE).")
                except Exception as e: logger.warning(f"  Błąd ekstrakcji licznika dla '{title}': {e}", exc_info=False)

                scanned_galleries.append({'url': gallery_url, 'title': title, 'count': count})

            except WebDriverException as wde: logger.warning(f"Błąd WebDrivera (może StaleElement) przy linku #{idx+1}: {wde}. Pomijam.")
            except Exception as e: logger.warning(f"Błąd przetwarzania linku #{idx+1} ({gallery_url}): {e}", exc_info=False)

        logger.info(f"Zakończono skanowanie dla '{model_name_original}'. Znaleziono {len(scanned_galleries)} unikalnych galerii.")
        return scanned_galleries
    except constants.RestartRequiredError: raise
    except Exception as e: logger.exception(f"Błąd skanowania {model_name_original}: {e}"); return []

def _determine_descriptive_foldername_base(driver, gallery_url, original_gallery_title_from_list, model_name_original_for_ai=None):
    folder_base_name = ""
    try:
        tags = driver.find_elements(By.CSS_SELECTOR, "div.pb-2 a.btn")
        cosplay = next((t.text.strip() for t in tags if '/cosplay/' in t.get_attribute('href')), "")
        fandom = next((t.text.strip() for t in tags if '/fandom/' in t.get_attribute('href')), "")
        if cosplay and fandom: folder_base_name = f"{cosplay} - {fandom}"
        elif cosplay: folder_base_name = cosplay
        elif fandom: folder_base_name = fandom
        if folder_base_name: logger.info(f"Nazwa z tagów (dla folderu): {folder_base_name}")
    except Exception as e: logger.warning(f"Błąd przy szukaniu tagów dla nazwy folderu: {e}", exc_info=False)

    if not folder_base_name:
        page_title = driver.title
        if page_title:
            logger.info(f"Tytuł strony do AI (dla nazwy folderu): {page_title}")
            if services.initialize_ai_model():
                negative_prompts_for_ai = [model_name_original_for_ai] if model_name_original_for_ai and isinstance(model_name_original_for_ai, str) else []
                ai_name = services.extract_gallery_name_t5(page_title, negative_prompts_list=negative_prompts_for_ai)
                processed_name = services.post_process_ai_title(ai_name)
                if processed_name:
                    folder_base_name = processed_name
                    logger.info(f"Nazwa z AI (dla folderu): {folder_base_name}")
                else: logger.warning(f"AI nie zwróciło użytecznej nazwy (dla folderu) z '{ai_name}'.")
            else: logger.warning("Model AI niedostępny, nie można użyć do ustalenia nazwy folderu.")
        else: logger.warning("Brak tytułu strony, nie można użyć AI do ustalenia nazwy folderu.")

    if not folder_base_name and original_gallery_title_from_list:
        logger.info(f"Używam oryginalnego tytułu '{original_gallery_title_from_list}' jako bazy dla nazwy folderu.")
        folder_base_name = original_gallery_title_from_list

    return utils.sanitize_foldername(folder_base_name or f"Galeria_{utils.get_gallery_id(gallery_url) or 'ID_Brak'}")

def determine_gallery_folder_path(model_data_dir, descriptive_base_name, gallery_id):
    safe_id = utils.sanitize_foldername(gallery_id)
    if descriptive_base_name and descriptive_base_name != f"Galeria_{safe_id}" and descriptive_base_name != "Nienazwana_Galeria":
        final_name = f"{descriptive_base_name}_{safe_id}"
    else:
        final_name = safe_id if safe_id else "Nienazwana_Galeria_BrakID"
    return os.path.join(model_data_dir, utils.sanitize_foldername(final_name))

def process_single_gallery(driver, model_name_original, gallery_info_scraped):
    config_handler.load_config()
    model_name_sanitized = utils.sanitize_foldername(model_name_original)
    model_galleries_data = data_manager.load_model_galleries_data(model_name_sanitized)

    gallery_url = gallery_info_scraped['url']
    title_from_scrape_or_queue = gallery_info_scraped['title']
    expected_count_from_scan = gallery_info_scraped.get('count')
    gallery_id = utils.get_gallery_id(gallery_url)

    if not gallery_id: logger.error(f"Brak ID dla URL: {gallery_url}. Pomijam."); return False

    gallery_entry = model_galleries_data.get(gallery_id, {})
    original_title_for_display = gallery_entry.get("determined_title") or gallery_entry.get("original_title_from_list") or title_from_scrape_or_queue or gallery_id
    model_data_dir = data_manager.get_model_data_dir(model_name_sanitized)
    initial_downloaded_count = gallery_entry.get("downloaded_count", 0)

    logger.debug(f"PSG: ID: {gallery_id} ('{original_title_for_display}'), Oczekiwane (scan/q): {expected_count_from_scan}, Pobrane (JSON): {initial_downloaded_count}")
    reporting.update_current_status("Przygotowanie galerii...", model=model_name_original, gallery=original_title_for_display, gallery_id=gallery_id, is_processing=True, downloaded_count=initial_downloaded_count, expected_count=expected_count_from_scan or gallery_entry.get("expected_count"))

    try:
        driver_utils.safe_driver_get(driver, gallery_url)
        determined_title = gallery_entry.get("determined_title") or _determine_descriptive_foldername_base(driver, gallery_url, title_from_scrape_or_queue, model_name_original)
        folder_path = gallery_entry.get("folder_path_on_disk") or determine_gallery_folder_path(model_data_dir, determined_title, gallery_id)
        os.makedirs(folder_path, exist_ok=True)

        expected_count = expected_count_from_scan
        if expected_count is None: expected_count = gallery_entry.get("expected_count"); logger.debug(f"PSG: Licznik (scan/q): BRAK. Z JSON: {expected_count}")
        else: logger.info(f"PSG: Licznik (scan/q): {expected_count}")

        should_check_gallery_page_count = (gallery_entry.get("status") not in ["completed", "completed_with_tolerance"]) or (expected_count is None)
        if should_check_gallery_page_count:
            logger.info(f"PSG: Spr. licznika na str. galerii '{gallery_id}' (obecny: {expected_count}).")
            try:
                count_el = driver.find_element(By.CSS_SELECTOR, "h1 > span.ms-1"); count_txt = count_el.text.strip()
                if count_txt.isdigit():
                    count_page = int(count_txt); logger.info(f"PSG: Licznik ze str. galerii: {count_page}.")
                    if expected_count is None or count_page > expected_count: expected_count = count_page; logger.info(f"PSG: Aktualizuję expected na {count_page}.")
                    elif count_page < expected_count: logger.warning(f"PSG: Licznik ze str. ({count_page}) < znanego ({expected_count}). Pozostaję przy większym.")
                else: logger.warning(f"PSG: Tekst licznika '{count_txt}' nie jest liczbą.")
            except NoSuchElementException: logger.warning(f"PSG: Brak licznika ('h1 > span.ms-1') na str. galerii '{gallery_id}'.")
            except Exception as e: logger.warning(f"PSG: Błąd pob. licznika ze str. galerii: {e}", exc_info=False)
        else: logger.info(f"PSG: Pomijam spr. licznika na str. galerii (status: {gallery_entry.get('status')}, expected: {expected_count}).")

        logger.info(f"PSG: Ostateczny expected_count dla '{determined_title}': {expected_count or '?'}")
        current_files_on_disk = set(os.listdir(folder_path)) if os.path.exists(folder_path) else set()
        final_dl_count = len(current_files_on_disk); new_dl_session = 0

        if expected_count is not None and final_dl_count >= expected_count:
            logger.info(f"PSG: Galeria '{determined_title}' ({gallery_id}) kompletna ({final_dl_count}/{expected_count}). Pomijam."); imgs_elements = []
        else:
            reporting.update_current_status(f"Przygotowanie do scrolla", model=model_name_original, gallery=determined_title, gallery_id=gallery_id, is_processing=True, downloaded_count=final_dl_count, expected_count=expected_count)
            imgs_elements = driver_utils.scroll_until_timeout(driver, 'div.photo-item a[href]', expected_count=expected_count, allow_up_scroll=False, gallery_id=gallery_id, model_name=model_name_original, gallery_title=determined_title, initial_downloaded_count=final_dl_count, current_expected_count_for_reporting=expected_count)

        if imgs_elements:
            logger.info(f"PSG: Pobieram dla {len(imgs_elements)} linków w '{determined_title}'. Na dysku: {final_dl_count}.")
            reporting.update_current_status(f"Pobieranie... ({final_dl_count})", model=model_name_original, gallery=determined_title, gallery_id=gallery_id, is_processing=True, downloaded_count=final_dl_count, scan_session_found_count=len(imgs_elements), expected_count=expected_count)
            for el in imgs_elements:
                if main.shutdown_requested: logger.info(f"PSG: Przerwano pobieranie dla {gallery_id}."); break
                try: img_url = el.get_attribute('href')
                except Exception as e: logger.warning(f"PSG: Błąd href: {e}", exc_info=False); continue
                if not img_url: continue
                img_filename = os.path.basename(utils.urlparse(img_url).path)
                if not img_filename: continue
                if img_filename not in current_files_on_disk:
                    if services.download_image(img_url, os.path.join(folder_path, img_filename)):
                        new_dl_session += 1; current_files_on_disk.add(img_filename); final_dl_count = len(current_files_on_disk)
                        reporting.update_current_status(f"Pobrano {new_dl_session} ({final_dl_count})...", model=model_name_original, gallery=determined_title, gallery_id=gallery_id, is_processing=True, downloaded_count=final_dl_count, scan_session_found_count=len(imgs_elements), expected_count=expected_count)
                time.sleep(0.01)
        else: logger.info(f"PSG: Brak elementów do pobrania dla '{determined_title}' ({gallery_id}).")

        final_dl_count = len(os.listdir(folder_path)) if os.path.exists(folder_path) else 0
        logger.info(f"PSG: '{determined_title}': pobrano {new_dl_session} nowych. Łącznie: {final_dl_count}. Oczekiwano: {expected_count or '?'}.")

        tolerance = config_handler.current_config['downloading']['incomplete_gallery_completion_tolerance']['value']
        status = "pending_check"; is_complete = False
        if expected_count is not None:
            if final_dl_count >= expected_count: status = "completed"; is_complete = True
            elif (expected_count - final_dl_count) <= tolerance and final_dl_count > 0: status = "completed_with_tolerance"; is_complete = True
            else: status = "partially_downloaded"
        elif final_dl_count > 0: status = "downloaded_unknown_total"
        logger.debug(f"PSG: Status galerii '{determined_title}': {status}")

        model_galleries_data[gallery_id] = {"url": gallery_url, "original_title_from_list": title_from_scrape_or_queue, "determined_title": determined_title, "folder_path_on_disk": folder_path, "expected_count": expected_count, "downloaded_count": final_dl_count, "status": status, "last_processed_timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
        incomplete_list = data_manager.load_incomplete_galleries()
        incomplete_list = [g for g in incomplete_list if g.get('url') != gallery_url]
        if not is_complete and expected_count is not None and final_dl_count < expected_count: incomplete_list.append({'url': gallery_url, 'expected': expected_count, 'downloaded': final_dl_count, 'folder': folder_path, 'model_name': model_name_original, 'gallery_title': determined_title})
        data_manager.save_incomplete_galleries(incomplete_list)
        data_manager.save_model_galleries_data(model_name_sanitized, model_galleries_data)

        time.sleep(0.25)

        pause = config_handler.current_config['pauses_and_rotation']['gallery_pause']['value']
        reporting.update_current_status("Pauza po galerii", model=model_name_original, gallery=determined_title, gallery_id=gallery_id, is_processing=False, downloaded_count=final_dl_count, expected_count=expected_count)
        time.sleep(pause * random.uniform(0.8, 1.2)); return True
    except constants.RestartRequiredError: reporting.update_current_status("Restart wymagany", model=model_name_original, gallery=original_title_for_display, gallery_id=gallery_id, is_processing=False); raise
    except Exception as e:
        logger.exception(f"PSG: Błąd krytyczny dla {gallery_id} ('{original_title_for_display}'): {e}")
        entry = model_galleries_data.get(gallery_id, {});
        entry.update({"url": gallery_url, "original_title_from_list": title_from_scrape_or_queue, "status": "error", "error_message": str(e)[:500], "last_processed_timestamp": time.strftime("%Y-%m-%d %H:%M:%S")})
        if "determined_title" not in entry: entry["determined_title"] = title_from_scrape_or_queue
        if "folder_path_on_disk" not in entry and 'folder_path' in locals() and locals()['folder_path']: entry["folder_path_on_disk"] = locals()['folder_path']
        elif "folder_path_on_disk" not in entry: entry["folder_path_on_disk"] = "Błąd - ścieżka nieustalona"
        model_galleries_data[gallery_id] = entry; data_manager.save_model_galleries_data(model_name_sanitized, model_galleries_data)
        reporting.update_current_status("Błąd galerii", model=model_name_original, gallery=original_title_for_display, gallery_id=gallery_id, is_processing=False)
        return False

def _update_model_profile_after_scan(model_name_original, scanned_gallery_infos, refresh_only=False):
    """Aktualizuje profil modelki na podstawie zeskanowanych danych."""
    model_name_sanitized = utils.sanitize_foldername(model_name_original)
    current_model_profile_data = data_manager.load_model_galleries_data(model_name_sanitized)
    profile_updated_flag = False
    galleries_to_process = []
    if not scanned_gallery_infos:
        logger.info(f"UMS: Brak galerii do aktualizacji dla {model_name_original}.")
        return []

    logger.info(f"UMS: Aktualizacja dla {model_name_original}. Zeskanowano: {len(scanned_gallery_infos)}. Tryb refresh_only: {refresh_only}")

    for scanned_info in scanned_gallery_infos:
        gid = utils.get_gallery_id(scanned_info['url'])
        if not gid: continue

        existing_entry = current_model_profile_data.get(gid, {})
        current_status = existing_entry.get("status")
        scanned_count = scanned_info.get('count')
        existing_count = existing_entry.get('expected_count')
        scanned_title = scanned_info['title']
        existing_title = existing_entry.get("original_title_from_list", gid)
        needs_processing = False
        needs_json_update = False

        if not existing_entry:
            logger.debug(f"UMS: Nowa galeria {gid} ('{scanned_title}', Licznik: {scanned_count}).")
            needs_processing = True
            needs_json_update = True
        else:
            title_changed = scanned_title and (scanned_title != existing_title or scanned_title != existing_entry.get("determined_title"))
            count_changed = scanned_count is not None and scanned_count != existing_count
            count_is_new_and_better = scanned_count is not None and (existing_count is None or scanned_count > existing_count)

            if title_changed:
                logger.info(f"UMS: Tytuł/Opis {gid} ('{existing_title}' -> '{scanned_title}').")
                needs_json_update = True
            if count_changed:
                logger.info(f"UMS: Licznik {gid} ('{scanned_title}') zmieniony ({existing_count} -> {scanned_count}).")
                needs_json_update = True
                # Uznaj za wymagające przetwarzania tylko, jeśli liczba wzrosła
                if count_is_new_and_better:
                    needs_processing = True

            # Jeśli galeria nie była kompletna, zawsze oznacz ją jako wymagającą sprawdzenia (jeśli nie refresh_only)
            if not needs_processing and current_status not in ["completed", "completed_with_tolerance"]:
                logger.debug(f"UMS: Galeria {gid} wymaga przetw. (status: {current_status}).")
                needs_processing = True
                needs_json_update = True # Upewnij się, że JSON się zapisze, nawet jeśli tylko status się zmieni

        if needs_json_update:
            profile_updated_flag = True
            new_entry = existing_entry.copy()
            new_entry.update({
                "url": scanned_info['url'],
                "original_title_from_list": scanned_title or existing_title,
                "expected_count": scanned_count if scanned_count is not None else existing_count,
                "determined_title": scanned_title or existing_entry.get("determined_title", gid),
            })
            # Jeśli wymaga przetwarzania, zmień status na pending_check (resetuje completed)
            if needs_processing:
                new_entry["status"] = "pending_check"
                new_entry["last_processed_timestamp"] = None
            # Jeśli nie było wpisu, a wymaga przetwarzania, ustaw status
            elif "status" not in new_entry and needs_processing:
                 new_entry["status"] = "pending_check"
            # Jeśli nie było wpisu i nie wymaga przetwarzania (nowa, ale refresh_only)
            elif "status" not in new_entry:
                 new_entry["status"] = "pending_check" # Nowe galerie zawsze powinny mieć status do sprawdzenia

            current_model_profile_data[gid] = new_entry

        # Dodaj do kolejki tylko jeśli nie jest to refresh_only i wymaga przetwarzania
        if needs_processing and not refresh_only:
            galleries_to_process.append({'url': scanned_info['url'], 'title': scanned_title or existing_title, 'count': scanned_count if scanned_count is not None else existing_count})

    if profile_updated_flag or not os.path.exists(data_manager.get_model_galleries_filepath(model_name_sanitized)):
        data_manager.save_model_galleries_data(model_name_sanitized, current_model_profile_data)
        logger.info(f"UMS: Profil '{model_name_sanitized}' zaktualizowany. Galerii: {len(current_model_profile_data)}")

    return galleries_to_process

def handle_priority_item(item, driver_instance=None):
    config_handler.load_config(); item_type = item.get("type"); payload = item.get("data")
    item_display_info = str(payload.get("id", str(payload))) if isinstance(payload, dict) else str(payload)
    if not item_type or payload is None: logger.warning(f"Nieprawidłowy element priorytetowy: {item}."); return
    logger.info(f"Priorytet: Typ='{item_type}', Dane='{item_display_info}'"); driver = None; created_here = False
    rre_occurred = False
    try:
        if item_type == "scan_model" or item_type == "scan_model_refresh_only": # <-- ZMIANA
            model_name = str(payload)
            is_refresh_only = item_type == "scan_model_refresh_only" # <-- NOWE
            status_msg = "Priorytet: Odświeżanie" if is_refresh_only else "Priorytet: Skan modelu"
            reporting.update_current_status(status_msg, model=model_name, is_processing=True) # <-- ZMIANA
            driver = driver_instance if driver_instance and driver_utils.is_driver_responsive(driver_instance) else driver_utils.create_driver_with_retry(); created_here = not (driver_instance and driver_utils.is_driver_responsive(driver_instance))
            scanned_infos = _scan_new_model_page(driver, model_name)
            to_process_from_scan = _update_model_profile_after_scan(model_name, scanned_infos, refresh_only=is_refresh_only) # <-- ZMIANA

            if to_process_from_scan: # Ta część wykona się tylko jeśli NIE jest refresh_only
                to_add_q = [{'type': 'gallery', 'data': {'id': utils.get_gallery_id(g['url']), 'model_name': model_name, 'title': g.get('title'), 'count': g.get('count')}} for g in to_process_from_scan if utils.get_gallery_id(g['url'])]
                if to_add_q: q = data_manager.load_priority_queue(); q = to_add_q + q; data_manager.save_priority_queue(q); logger.info(f"Dodano {len(to_add_q)} galerii z '{model_name}' do kolejki.")
            elif is_refresh_only: # Logujemy jeśli to było tylko odświeżanie
                 logger.info(f"Odświeżanie opisów dla '{model_name}' zakończone. Nie dodano galerii do kolejki.")

            time.sleep(0.25); reporting.generate_global_html_status(); reporting.update_current_status(f"Zakończono skan/odświeżanie {model_name}", model=model_name, is_processing=False); return
        elif item_type == "gallery":
            if not isinstance(payload, dict): logger.error(f"Błąd 'gallery': Oczekiwano dict w 'data', jest: {type(payload)}. Element: {item}"); return
            gid, model, title, count = payload.get("id"), payload.get("model_name"), payload.get("title"), payload.get("count")
            if not gid or not model: logger.error(f"Brak ID/Modelu w 'gallery': {payload}."); return
            reporting.update_current_status("Priorytet: Przetw. galerii", gallery_id=gid, model=model, gallery=title, is_processing=True)
            driver = driver_instance if driver_instance and driver_utils.is_driver_responsive(driver_instance) else driver_utils.create_driver_with_retry(); created_here = not (driver_instance and driver_utils.is_driver_responsive(driver_instance))
            services.initialize_ai_model()
            profile_g = data_manager.load_model_galleries_data(utils.sanitize_foldername(model)).get(gid)
            url_g = profile_g.get('url') if profile_g else f"{constants.BASE_URL_SITE}/gallery/{gid}"
            info_g = {'url': url_g, 'title': title or gid, 'count': count if count is not None else (profile_g.get('expected_count') if profile_g else None)}
            process_single_gallery(driver, model, info_g)
            time.sleep(0.25); reporting.generate_global_html_status()
            logger.info(f"Zakończono priorytet {gid} dla {model}."); reporting.update_current_status(f"Zakończono galerię {title}", model=model, gallery_id=gid, gallery=title, is_processing=False)
    except constants.RestartRequiredError as rre:
        rre_occurred = True
        logger.warning(f"RRE w handle_priority_item: {rre}.");
        if created_here and driver:
            try:
                driver.quit()
                logger.info("Zamknięto driver (HPI) po RRE (utworzony lokalnie).")
            except Exception as e:
                logger.warning(f"Błąd quit HPI RRE: {e}")
        raise
    except Exception as e:
        logger.exception(f"Błąd priorytetu {item_display_info}: {e}");
        reporting.update_current_status(f"Błąd kryt. prio {item_type} - {item_display_info}", is_processing=False)
    finally:
        if driver and created_here and not rre_occurred:
            logger.info(f"Zamykam driver HPI (finally, no RRE) dla {item_display_info}");
            try:
                driver.quit()
            except Exception as e:
                logger.warning(f"Błąd quit HPI finally (no RRE): {e}")

        exception_other_than_rre = 'e' in locals() and not isinstance(locals().get('e'), constants.RestartRequiredError)
        if not main.shutdown_requested and not rre_occurred and not exception_other_than_rre:
            if not data_manager.load_script_state().get("current_operation",{}).get("name"):
                 reporting.update_current_status("Oczekiwanie...",is_processing=False)

def handle_process_models(start_model_index=0, check_mode="all_or_incomplete"):
    models_list = data_manager.read_model_list()
    if not models_list: logger.info("Brak modelek."); data_manager.clear_active_operation(); return
    driver = None; g_processed_vpn = 0; last_err = None
    config_handler.load_config(); cfg_pr = config_handler.current_config['pauses_and_rotation']
    vpn_thresh = random.randint(cfg_pr['GALLERY_PAUSE_THRESHOLD_MIN']['value'], cfg_pr['GALLERY_PAUSE_THRESHOLD_MAX']['value'])
    logger.info(f"Start HPM. Tryb: {check_mode}. Start: {start_model_index}. Próg VPN: {vpn_thresh}.")
    err_stop = False
    try:
        driver = driver_utils.create_driver_with_retry(); services.initialize_ai_model()
        for model_idx in range(start_model_index, len(models_list)):
            if main.shutdown_requested or err_stop: logger.info("HPM: Stop/Shutdown."); break
            if config_handler.load_config(): logger.info("HPM: Config przeładowany.")

            prio_batch_count = 0
            while True:
                if main.shutdown_requested: err_stop=True; break
                p_q = data_manager.load_priority_queue()
                if not p_q: break
                if prio_batch_count >= 5: logger.info(f"HPM: Przetworzono {prio_batch_count} prio. Kontynuuję model."); break

                logger.info(f"HPM: {len(p_q)} prio. Przetwarzam...");
                item_p = p_q.pop(0);
                data_manager.save_priority_queue(p_q)

                try:
                    handle_priority_item(item_p, driver_instance=driver)
                except constants.RestartRequiredError as rre_p:
                    logger.warning(f"RRE w prio {item_p}: {rre_p}.")
                    if not driver_utils.is_driver_responsive(driver):
                        driver = driver_utils.create_driver_with_retry()
                    raise rre_p
                except Exception as e_p:
                    logger.exception(f"Błąd w prio {item_p}: {e_p}")
                    if not driver_utils.is_driver_responsive(driver):
                        logger.warning("Driver niereponsywny po błędzie prio. Odtwarzam.")
                        try:
                            driver.quit()
                        except:
                            pass
                        driver = driver_utils.create_driver_with_retry()
                prio_batch_count+=1
            if err_stop: break

            model_name = models_list[model_idx]; model_sani = utils.sanitize_foldername(model_name)
            reporting.update_current_status(f"Model ({check_mode})", model=model_name, is_processing=True)
            logger.info(f"=== MODEL: {model_name} ({model_idx+1}/{len(models_list)}) ==="); os.makedirs(data_manager.get_model_data_dir(model_sani), exist_ok=True)
            profile_d = data_manager.load_model_galleries_data(model_sani)
            profile_ex = os.path.exists(data_manager.get_model_galleries_filepath(model_sani))
            g_to_process = []
            scan_page = (check_mode == "only_new_or_count_changed") or (check_mode == "all_or_incomplete" and (not profile_ex or not profile_d))
            if scan_page:
                logger.info(f"HPM: Skanuję {model_name}...");
                try:
                    scanned_g = _scan_new_model_page(driver, model_name)
                    g_to_process.extend(_update_model_profile_after_scan(model_name, scanned_g))
                    time.sleep(0.25); reporting.generate_global_html_status()
                    if main.shutdown_requested: err_stop=True; break
                except constants.RestartRequiredError: raise
                except Exception as e_s:
                    logger.error(f"HPM: Błąd skanu {model_name}: {e_s}", exc_info=True); last_err=e_s;
                    data_manager.update_last_model_index(model_idx); time.sleep(0.25); reporting.generate_global_html_status();
                    if main.shutdown_requested: err_stop=True; break
                    continue
            elif check_mode == "all_or_incomplete" and profile_ex and profile_d:
                 logger.info(f"HPM: Nieukończone z profilu {model_name}.");
                 for gid, g_e in profile_d.items():
                     if g_e.get("status") not in ["completed", "completed_with_tolerance"]: g_to_process.append({'url': g_e['url'], 'title': g_e.get('original_title_from_list',gid), 'count': g_e.get('expected_count')})
                 if g_to_process: logger.info(f"Znaleziono {len(g_to_process)} nieukończonych.")
            if err_stop: break
            if not g_to_process: logger.info(f"HPM: Brak galerii do przetworzenia dla {model_name}.");
            else: logger.info(f"HPM: Przetwarzam {len(g_to_process)} galerii dla {model_name}...")

            for g_info in g_to_process:
                if main.shutdown_requested: err_stop=True; break
                if data_manager.load_priority_queue():
                    logger.info("HPM: Wykryto prio. Przerywam model.")
                    data_manager.update_last_model_index(model_idx)
                    return
                try:
                    process_single_gallery(driver, model_name, g_info)
                except constants.RestartRequiredError as rre_g:
                    logger.warning(f"RRE w galerii {g_info.get('title')}: {rre_g}.")
                    raise
                except Exception as e_g:
                    logger.exception(f"Błąd w galerii {g_info.get('title')}: {e_g}")
                    last_err=e_g

                if main.shutdown_requested: err_stop=True; break

                g_processed_vpn+=1
                time.sleep(0.25)
                reporting.generate_global_html_status()
                if g_processed_vpn >= vpn_thresh:
                    logger.info(f"Próg VPN ({g_processed_vpn}). Restart.")
                    data_manager.update_last_model_index(model_idx)
                    raise constants.RestartRequiredError("Próg VPN")
            if err_stop: break

            data_manager.update_last_model_index(model_idx);
            reporting.update_current_status(f"Zakończono model {model_name}", model=model_name, is_processing=False);
            time.sleep(0.25); reporting.generate_global_html_status();
            logger.info(f"--- Zakończono model {model_name} ---")

        if not main.shutdown_requested and not err_stop:
            logger.info(f"🎉 HPM: ZAKOŃCZONO ({check_mode}) 🎉");
            data_manager.update_last_model_index(-1);
            data_manager.clear_active_operation()
    except constants.RestartRequiredError as rre_o:
        last_err=rre_o;
        logger.warning(f"RRE w HPM: {rre_o}.");
        raise
    except Exception as e_o:
        last_err=e_o;
        logger.exception(f"Błąd krytyczny HPM: {e_o}");
        data_manager.clear_active_operation()
    finally:
        if driver:
            logger.info("Zamykam driver (finally HPM)...")
            try:
                driver.quit()
            except Exception as e_q:
                logger.warning(f"Błąd zamykania drivera w HPM: {e_q}")

        is_rre_f = isinstance(last_err, constants.RestartRequiredError)
        if not main.shutdown_requested and not is_rre_f:
            op_s = data_manager.load_script_state().get("current_operation",{});
            msg_f = "Zakończono/Przerwano modele."
            if not op_s.get("name"): msg_f = "Zakończono modele. Oczekiwanie."
            reporting.update_current_status(msg_f, is_processing=False)
        time.sleep(0.25); reporting.generate_global_html_status()

def handle_fill_incomplete():
    reporting.update_current_status("Uzupełnianie niekompletnych", is_processing=True)
    entries = data_manager.load_incomplete_galleries()
    if not entries: logger.info("HFI: Brak niekompletnych."); reporting.update_current_status("Brak niekompletnych.", is_processing=False); data_manager.clear_active_operation(); return
    logger.info(f"HFI: Uzupełniam {len(entries)} galerii...")
    driver = None; processed_any = False; err_stop_fill = False; last_err_hfi = None
    try:
        driver = driver_utils.create_driver_with_retry(); services.initialize_ai_model()
        for idx, entry in enumerate(entries):
            if main.shutdown_requested: logger.info("HFI: Przerwano."); err_stop_fill=True; break
            if config_handler.load_config(): logger.info("HFI: Config przeładowany.")
            if data_manager.load_priority_queue(): logger.info("HFI: Wykryto priorytety. Przerywam."); return
            title_d = entry.get('gallery_title', entry.get('url','N/A')); logger.info(f"HFI [{idx+1}/{len(entries)}]: '{title_d}' ({entry.get('model_name','N/A')})")
            s_mock = {'url': entry['url'], 'title': entry.get('gallery_title'), 'count': entry.get('expected')}
            try:
                if process_single_gallery(driver, entry['model_name'], s_mock): processed_any=True
            except constants.RestartRequiredError as rre_f: logger.warning(f"RRE w HFI dla '{title_d}': {rre_f}."); raise
            except Exception as e_f: logger.exception(f"Błąd HFI dla '{title_d}': {e_f}"); last_err_hfi=e_f
            if main.shutdown_requested: err_stop_fill=True; break
            time.sleep(0.25); reporting.generate_global_html_status()
        if not main.shutdown_requested and not err_stop_fill:
            logger.info("✅ HFI: Zakończono pętlę."); data_manager.clear_active_operation()
            msg_e = "Zakończono uzupełnianie." if processed_any else "Uzupełnianie zakończone (bez postępu/błędów)."
            if not entries: msg_e = "Brak galerii do uzupełnienia."
            reporting.update_current_status(msg_e, is_processing=False)
    except constants.RestartRequiredError as rre_h: last_err_hfi=rre_h; logger.warning(f"RRE w HFI: {rre_h}."); raise
    except Exception as e_h: last_err_hfi=e_h; logger.exception(f"Błąd krytyczny HFI: {e_h}"); data_manager.clear_active_operation()
    finally:
        if driver:
            logger.info("Zamykam driver (finally HFI)...")
            try:
                driver.quit()
            except Exception as e_qf:
                logger.warning(f"Błąd zamykania drivera w HFI: {e_qf}")
        is_rre_fin_hfi = isinstance(last_err_hfi, constants.RestartRequiredError)
        if not main.shutdown_requested and not is_rre_fin_hfi:
            op_st_f = data_manager.load_script_state().get("current_operation",{})
            fin_m = "Zakończono/Przerwano uzupełnianie."
            if not op_st_f.get("name"):
                fin_m = "Zakończono uzupełnianie." if processed_any and not err_stop_fill else "Uzupełnianie zakończone (bez postępu/błędów)."
                if not entries: fin_m = "Brak galerii do uzupełnienia."
            if not err_stop_fill or not op_st_f.get("name"): reporting.update_current_status(fin_m, is_processing=False)
        time.sleep(0.25); reporting.generate_global_html_status()