# -*- coding: utf-8 -*-
import os
import time
import random
import traceback
from selenium.webdriver.common.by import By

import constants
import config_handler # <-- Dodano import
import utils
import data_manager
import driver_utils
import services
import reporting

def _determine_descriptive_foldername_base(driver, gallery_url, original_gallery_title_from_list):
    folder_base_name = ""
    try:
        tags = driver.find_elements(By.CSS_SELECTOR, "div.pb-2 a.btn")
        cosplay = next((t.text.strip() for t in tags if '/cosplay/' in t.get_attribute('href')), "")
        fandom = next((t.text.strip() for t in tags if '/fandom/' in t.get_attribute('href')), "")
        if cosplay and fandom: folder_base_name = f"{cosplay} - {fandom}"
        elif cosplay: folder_base_name = cosplay
        elif fandom: folder_base_name = fandom
        if folder_base_name: print(f"INFO_DETAIL: Nazwa z tagów: {folder_base_name}")
    except Exception as e: print(f"WARN_DETAIL: Błąd przy szukaniu tagów: {e}")

    if not folder_base_name:
        page_title = driver.title
        if page_title:
            print(f"INFO_DETAIL: Tytuł strony do AI: {page_title}")
            if services.initialize_ai_model():
                ai_name = services.extract_gallery_name_t5(page_title)
                processed_name = services.post_process_ai_title(ai_name)
                if processed_name:
                    folder_base_name = processed_name
                    print(f"INFO_DETAIL: Nazwa z AI: {folder_base_name}")
                else: print(f"WARN_DETAIL: AI nie dało dobrej nazwy ('{ai_name}').")
            else: print("WARN_DETAIL: Model AI niedostępny.")

    if not folder_base_name: folder_base_name = original_gallery_title_from_list

    return utils.sanitize_foldername(folder_base_name or "Nienazwana_Galeria")

def determine_gallery_folder_path(model_data_dir, descriptive_base_name, gallery_id):
    safe_id = utils.sanitize_foldername(gallery_id)
    final_name = f"{descriptive_base_name}_{safe_id}" if descriptive_base_name != "Nienazwana_Galeria" else safe_id
    return os.path.join(model_data_dir, utils.sanitize_foldername(final_name))


def process_single_gallery(driver, model_name_original, gallery_info_scraped):
    config_handler.load_config() # <-- Sprawdź config przed każdą galerią
    model_name_sanitized = utils.sanitize_foldername(model_name_original)
    model_galleries_data = data_manager.load_model_galleries_data(model_name_sanitized)

    gallery_url = gallery_info_scraped['url']
    original_title = gallery_info_scraped['title']
    expected_count_list = gallery_info_scraped.get('count')
    gallery_id = utils.get_gallery_id(gallery_url)

    gallery_entry = model_galleries_data.get(gallery_id, {})
    model_data_dir = data_manager.get_model_data_dir(model_name_sanitized)
    initial_downloaded_count_from_json = gallery_entry.get("downloaded_count", 0)

    print(f"\nDEBUG_PSG: Rozpoczynam process_single_gallery dla ID: {gallery_id}, URL: {gallery_url}")
    print(f"DEBUG_PSG: Oryginalny tytuł: '{original_title}', Oczekiwane z listy/wejścia: {expected_count_list}")
    print(f"DEBUG_PSG: Wpis z JSON (gallery_entry): {gallery_entry}")
    print(f"DEBUG_PSG: Początkowo pobranych (z JSON): {initial_downloaded_count_from_json}")

    reporting.update_current_status(
        "Przygotowanie galerii...", model=model_name_original,
        gallery=original_title, gallery_id=gallery_id, is_processing=True,
        downloaded_count=initial_downloaded_count_from_json,
        scan_session_found_count=0
    )

    try:
        print(f"DEBUG_PSG: Wywołuję safe_driver_get dla {gallery_url}")
        driver_utils.safe_driver_get(driver, gallery_url)
        print(f"DEBUG_PSG: safe_driver_get zakończony. Tytuł strony: {driver.title}")

        determined_title = gallery_entry.get("determined_title") or \
                           _determine_descriptive_foldername_base(driver, gallery_url, original_title)

        folder_path = gallery_entry.get("folder_path_on_disk") or \
                      determine_gallery_folder_path(model_data_dir, determined_title, gallery_id)

        print(f"DEBUG_PSG: Ustalony tytuł: {determined_title}, Folder: {folder_path}")
        os.makedirs(folder_path, exist_ok=True)

        expected_count = expected_count_list
        if expected_count is None:
            expected_count = gallery_entry.get("expected_count")
        if expected_count is None:
            print(f"DEBUG_PSG: expected_count jest None, próbuję pobrać ze strony...")
            try:
                expected_count_element = driver.find_element(By.CSS_SELECTOR, "h1 > span.ms-1")
                expected_count = int(expected_count_element.text.strip())
                print(f"DEBUG_PSG: Pobrane expected_count ze strony: {expected_count}")
            except Exception as e_scrape_count:
                print(f"DEBUG_PSG: Nie udało się pobrać expected_count ze strony: {e_scrape_count}")
                expected_count = None
        print(f"DEBUG_PSG: Ostateczne 'expected_count' przed scroll: {expected_count or '?'}")

        current_downloads_on_disk_before_scan = len(os.listdir(folder_path))
        print(f"DEBUG_PSG: Plików na dysku przed skanowaniem: {current_downloads_on_disk_before_scan}")

        print(f"DEBUG_PSG: Wywołuję scroll_until_timeout...")
        imgs_elements = driver_utils.scroll_until_timeout(
            driver,
            'div.photo-item a[href]',
            expected_count,
            allow_up_scroll=False,
            gallery_id=gallery_id,
            model_name=model_name_original,
            gallery_title=determined_title,
            initial_downloaded_count=current_downloads_on_disk_before_scan,
            current_expected_count_for_reporting=expected_count
        )
        print(f"DEBUG_PSG: scroll_until_timeout zwrócił {len(imgs_elements)} elementów.")

        current_downloads_on_disk = len(os.listdir(folder_path))
        reporting.update_current_status(
            f"Pobieranie... ({current_downloads_on_disk})", model=model_name_original,
            gallery=determined_title, gallery_id=gallery_id, is_processing=True,
            downloaded_count=current_downloads_on_disk,
            scan_session_found_count=None,
            expected_count=expected_count
        )

        existing_files_on_disk = set(os.listdir(folder_path))
        newly_downloaded_this_session = 0

        if imgs_elements:
            print(f"DEBUG_PSG: Rozpoczynam pętlę pobierania {len(imgs_elements)} elementów.")
            for el_idx, el in enumerate(imgs_elements):
                config_handler.load_config() # <-- Sprawdź config wewnątrz pętli pobierania
                try: img_url = el.get_attribute('href')
                except Exception: continue
                if not img_url: continue
                img_filename = os.path.basename(utils.urlparse(img_url).path)
                if not img_filename: continue

                if img_filename not in existing_files_on_disk:
                    if services.download_image(img_url, os.path.join(folder_path, img_filename)):
                        newly_downloaded_this_session += 1
                        current_downloads_on_disk +=1
                        existing_files_on_disk.add(img_filename)
                        reporting.update_current_status(
                            f"Pobieranie... ({current_downloads_on_disk})", model=model_name_original,
                            gallery=determined_title, gallery_id=gallery_id, is_processing=True,
                            downloaded_count=current_downloads_on_disk,
                            scan_session_found_count=None,
                            expected_count=expected_count
                        )
                time.sleep(0.05)
            print(f"DEBUG_PSG: Pętla pobierania zakończona.")
        else:
            print(f"DEBUG_PSG: Brak elementów (imgs_elements) do pobrania.")


        final_count_on_disk = len(os.listdir(folder_path))
        print(f"DEBUG_PSG: Pobrano {newly_downloaded_this_session} nowych. Łącznie na dysku: {final_count_on_disk}")

        tolerance = config_handler.current_config['downloading']['incomplete_gallery_completion_tolerance']['value']
        status = "pending_check"; is_complete = False
        if expected_count is not None:
            if final_count_on_disk >= expected_count: status = "completed"; is_complete = True
            elif (expected_count - final_count_on_disk) <= tolerance and final_count_on_disk > 0 : status = "completed_with_tolerance"; is_complete = True
            else: status = "partially_downloaded"
        elif final_count_on_disk > 0: status = "downloaded_unknown_total"
        print(f"DEBUG_PSG: Status galerii: {status}")

        model_galleries_data[gallery_id] = {
            "url": gallery_url, "original_title_from_list": original_title,
            "determined_title": determined_title, "folder_path_on_disk": folder_path,
            "expected_count": expected_count, "downloaded_count": final_count_on_disk,
            "status": status, "last_processed_timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        incomplete_list = data_manager.load_incomplete_galleries()
        incomplete_list = [g for g in incomplete_list if g.get('url') != gallery_url]
        if not is_complete and expected_count is not None and final_count_on_disk < expected_count:
            incomplete_list.append({
                'url': gallery_url, 'expected': expected_count, 'downloaded': final_count_on_disk,
                'folder': folder_path, 'model_name': model_name_original, 'gallery_title': determined_title
            })
        data_manager.save_incomplete_galleries(incomplete_list)
        data_manager.save_model_galleries_data(model_name_sanitized, model_galleries_data)

        pause = config_handler.current_config['pauses_and_rotation']['gallery_pause']['value']
        reporting.update_current_status(
            "Pauza po galerii", model=model_name_original, gallery=determined_title,
            gallery_id=gallery_id, is_processing=False, downloaded_count=final_count_on_disk
        )
        time.sleep(pause * random.uniform(0.8, 1.2))
        return True

    except constants.RestartRequiredError:
        print(f"DEBUG_PSG: RestartRequiredError w process_single_gallery dla {gallery_id}")
        reporting.update_current_status("Restart wymagany", model=model_name_original, gallery=original_title, gallery_id=gallery_id, is_processing=False)
        raise
    except Exception as e:
        print(f"DEBUG_PSG: Exception w process_single_gallery dla {gallery_id}: {e}"); traceback.print_exc()
        model_galleries_data[gallery_id] = model_galleries_data.get(gallery_id, {})
        model_galleries_data[gallery_id].update({
            "url": gallery_url, "original_title_from_list": original_title, "status": "error",
            "error_message": str(e), "last_processed_timestamp": time.strftime("%Y-%m-%d %H:%M:%S")})
        data_manager.save_model_galleries_data(model_name_sanitized, model_galleries_data)
        reporting.update_current_status("Błąd galerii", model=model_name_original, gallery=original_title, gallery_id=gallery_id, is_processing=False)
        return False

def _scan_new_model_page(driver, model_name_original):
    config_handler.load_config() # <-- Sprawdź config przed skanowaniem
    print(f"   🔍 Skanuję stronę nowej modelki: {model_name_original}")
    model_page_url = f"{constants.BASE_URL_SITE}/model/{model_name_original.lower().replace(' ', '-')}"
    driver_utils.safe_driver_get(driver, model_page_url)
    links = driver_utils.scroll_until_timeout(driver, 'a[style*="text-shadow"]', allow_up_scroll=True)
    scraped_galleries = []
    for el in links:
        href = el.get_attribute('href'); title = el.text.strip(); count = None
        try: count = int(el.find_element(By.XPATH, './ancestor::div[contains(@class,"grid-item")]//span.ms-1').text)
        except Exception: pass
        if href and '/gallery/' in href and title:
            scraped_galleries.append({'url': href, 'title': title, 'count': count})
    print(f"   🔎 Znaleziono {len(scraped_galleries)} galerii na stronie.")
    return scraped_galleries


def handle_priority_item(item, driver_instance=None):
    config_handler.load_config() # <-- Sprawdź config na początku
    item_type = item.get("type")
    item_id = item.get("id")

    if not item_type or not item_id:
        print(f"  ⚠️ Nieprawidłowy element priorytetowy: {item}. Pomijam.")
        return

    print(f"   ⬆️ Przetwarzanie priorytetowe: {item_type} - {item_id}")
    driver = None
    created_here = False

    try:
        if item_type == "scan_model":
            model_name_original = item_id
            reporting.update_current_status("Priorytet: Skanowanie nowego modelu", model=model_name_original)
            driver = driver_utils.create_driver_with_retry(); created_here = True
            scraped_galleries = _scan_new_model_page(driver, model_name_original)

            if scraped_galleries:
                model_name_sanitized = utils.sanitize_foldername(model_name_original)
                new_model_data = data_manager.load_model_galleries_data(model_name_sanitized)
                galleries_to_add_to_queue = []
                for gal_info in scraped_galleries:
                    gid = utils.get_gallery_id(gal_info['url'])
                    if gid not in new_model_data or new_model_data[gid].get('status') == 'pending_check':
                        new_model_data[gid] = {
                            "url": gal_info['url'], "original_title_from_list": gal_info['title'],
                            "determined_title": None, "folder_path_on_disk": None,
                            "expected_count": gal_info.get('count'), "downloaded_count": 0,
                            "status": "pending_check", "last_processed_timestamp": None
                        }
                        galleries_to_add_to_queue.append({"type": "gallery", "id": gid})

                data_manager.save_model_galleries_data(model_name_sanitized, new_model_data)
                if galleries_to_add_to_queue:
                    queue = data_manager.load_priority_queue()
                    new_queue = galleries_to_add_to_queue + queue
                    data_manager.save_priority_queue(new_queue)
                    print(f"      Dodano {len(galleries_to_add_to_queue)} galerii z '{model_name_original}' do kolejki priorytetowej.")
                else:
                    print(f"      Brak nowych galerii do dodania do kolejki dla '{model_name_original}' po skanowaniu.")
                reporting.generate_global_html_status()
            else:
                 print(f"      ⚠️ Nie znaleziono galerii dla '{model_name_original}' podczas skanowania.")
            return

        elif item_type == "model":
             reporting.update_current_status("Priorytet: Dodawanie modelu", model=item_id)
             model_name_sanitized = utils.sanitize_foldername(item_id)
             model_galleries = data_manager.load_model_galleries_data(model_name_sanitized)
             added_count = 0
             for gid, ginfo in model_galleries.items():
                 if ginfo.get("status") not in ["completed", "completed_with_tolerance"]:
                     if data_manager.add_to_priority_queue("gallery", gid): added_count += 1
             print(f"      Dodano {added_count} nieukończonych galerii z modelu {item_id} do kolejki.")
             return

        elif item_type == "gallery":
            gallery_id_to_process = item_id
            found_model, found_gallery_info = None, None
            for model_name_iter in data_manager.read_model_list():
                galleries_data = data_manager.load_model_galleries_data(utils.sanitize_foldername(model_name_iter))
                if gallery_id_to_process in galleries_data:
                    found_model, found_gallery_info = model_name_iter, galleries_data[gallery_id_to_process]; break

            if not found_model:
                print(f"   ❌ Nie znaleziono galerii {gallery_id_to_process}. Pomijam."); return

            if driver_instance:
                driver = driver_instance
                print(f"DEBUG_HP: Używam istniejącego drivera dla priorytetu galerii {gallery_id_to_process}")
            else:
                print(f"DEBUG_HP: Tworzę nowy driver dla priorytetu galerii {gallery_id_to_process}")
                driver = driver_utils.create_driver_with_retry(); created_here = True

            services.initialize_ai_model()
            scraped_info_mock = {
                'url': found_gallery_info.get('url'),
                'title': found_gallery_info.get('original_title_from_list', found_gallery_info.get('determined_title', gallery_id_to_process)),
                'count': found_gallery_info.get('expected_count')
            }
            process_single_gallery(driver, found_model, scraped_info_mock)
            reporting.generate_global_html_status()
            print(f"   ✅ Zakończono priorytet galerii {gallery_id_to_process}.")

    except constants.RestartRequiredError: raise
    except Exception as e: print(f"   💥 Błąd priorytetu {item_id}: {e}"); traceback.print_exc()
    finally:
        if driver and created_here:
            print(f"DEBUG_HP: Zamykam driver utworzony w handle_priority_item dla {item_id}")
            driver.quit()
        reporting.update_current_status("Zakończono zadanie priorytetowe", is_processing=False)


def handle_process_models(start_model_index=0, check_mode="all_or_incomplete"):
    models_list = data_manager.read_model_list()
    if not models_list: print("🚫 Brak modelek na liście."); return

    driver = None
    galleries_processed_since_vpn_rotation = 0
    # Ładowanie configu tutaj, aby pobrać początkowe wartości progów
    config_handler.load_config()
    cfg_pause_rotation = config_handler.current_config['pauses_and_rotation']
    vpn_rotation_threshold = random.randint(cfg_pause_rotation['GALLERY_PAUSE_THRESHOLD_MIN']['value'], cfg_pause_rotation['GALLERY_PAUSE_THRESHOLD_MAX']['value'])
    print(f"ℹ️ Próg rotacji VPN: {vpn_rotation_threshold} galerii.")

    try:
        driver = driver_utils.create_driver_with_retry()

        for model_idx in range(start_model_index, len(models_list)):
            config_handler.load_config() # <-- Sprawdź config przed każdym modelem

            # Zaktualizuj próg rotacji, jeśli config się zmienił
            cfg_pause_rotation_new = config_handler.current_config['pauses_and_rotation']
            if cfg_pause_rotation_new != cfg_pause_rotation:
                 cfg_pause_rotation = cfg_pause_rotation_new
                 vpn_rotation_threshold = random.randint(cfg_pause_rotation['GALLERY_PAUSE_THRESHOLD_MIN']['value'], cfg_pause_rotation['GALLERY_PAUSE_THRESHOLD_MAX']['value'])
                 print(f"   🔄 Zaktualizowano próg rotacji VPN: {vpn_rotation_threshold} galerii.")

            while True:
                priority_queue = data_manager.load_priority_queue()
                if not priority_queue: break
                item_to_process = priority_queue.pop(0)
                data_manager.save_priority_queue(priority_queue)
                handle_priority_item(item_to_process)

            model_name_original_iter = models_list[model_idx]
            model_name_sanitized_iter = utils.sanitize_foldername(model_name_original_iter)
            reporting.update_current_status(f"Przetwarzanie modelu ({check_mode})", model=model_name_original_iter)
            print(f"\n⭐️=== MODEL: {model_name_original_iter} ({model_idx + 1}/{len(models_list)}) ===")

            os.makedirs(data_manager.get_model_data_dir(model_name_sanitized_iter), exist_ok=True)
            current_model_galleries_data = data_manager.load_model_galleries_data(model_name_sanitized_iter)
            model_galleries_path = data_manager.get_model_galleries_filepath(model_name_sanitized_iter)
            profile_exists = os.path.exists(model_galleries_path)
            galleries_to_process_this_model = []

            model_page_url = f"{constants.BASE_URL_SITE}/model/{model_name_original_iter.lower().replace(' ', '-')}"
            should_scan_page = (check_mode == "only_new_or_count_changed" and profile_exists) or \
                               (check_mode == "all_or_incomplete" and not profile_exists)

            if should_scan_page:
                print(f"   🔍 Skanuję stronę: {model_page_url}")
                try:
                    scraped_galleries_on_page = _scan_new_model_page(driver, model_name_original_iter)
                    if check_mode == "only_new_or_count_changed":
                        for scraped_info_item in scraped_galleries_on_page:
                            gid = utils.get_gallery_id(scraped_info_item['url'])
                            known_entry = current_model_galleries_data.get(gid)
                            if not known_entry or \
                               (scraped_info_item.get('count') is not None and \
                                known_entry.get('expected_count') is not None and \
                                scraped_info_item['count'] > known_entry['expected_count']):
                                 galleries_to_process_this_model.append(scraped_info_item); print(f"      ➕ Nowa/Zaktualizowana: {scraped_info_item['title']}")
                    else:
                        galleries_to_process_this_model = scraped_galleries_on_page
                        if not profile_exists:
                            new_model_data_for_json = {}
                            for gal_info_item in scraped_galleries_on_page:
                                gid = utils.get_gallery_id(gal_info_item['url'])
                                new_model_data_for_json[gid] = {
                                    "url": gal_info_item['url'],
                                    "original_title_from_list": gal_info_item['title'],
                                    "expected_count": gal_info_item.get('count'),
                                    "status": "pending_check",
                                    "downloaded_count": 0
                                }
                            data_manager.save_model_galleries_data(model_name_sanitized_iter, new_model_data_for_json)
                            current_model_galleries_data = new_model_data_for_json

                except constants.RestartRequiredError: raise
                except Exception as e_page_load: print(f"   ❌ Błąd strony {model_name_original_iter}: {e_page_load}. Pomijam."); continue

            elif check_mode == "all_or_incomplete" and profile_exists:
                 print("   ℹ️ Kontynuuję nieukończone galerie (profil istnieje).")
                 for gid, gallery_entry_data in current_model_galleries_data.items():
                     if gallery_entry_data.get("status") not in ["completed", "completed_with_tolerance"]:
                         galleries_to_process_this_model.append({
                             'url': gallery_entry_data['url'],
                             'title': gallery_entry_data.get('original_title_from_list', gid),
                             'count': gallery_entry_data.get('expected_count')
                         })
                 print(f"      Znaleziono {len(galleries_to_process_this_model)} nieukończonych galerii.")

            if not galleries_to_process_this_model: print("   🏁 Brak galerii do przetworzenia dla tego modelu.");
            else: print(f"   ⚙️ Przetwarzam {len(galleries_to_process_this_model)} galerii dla {model_name_original_iter}...")

            data_changed_for_model = False
            for gallery_info_to_process_item in galleries_to_process_this_model:
                 if data_manager.load_priority_queue():
                     print("   ⬆️ Wykryto zadania priorytetowe. Przerywam przetwarzanie modelu.");
                     if data_changed_for_model: data_manager.save_model_galleries_data(model_name_sanitized_iter, current_model_galleries_data)
                     raise constants.RestartRequiredError("Przerwanie dla kolejki priorytetowej", no_vpn=True)

                 if process_single_gallery(driver, model_name_original_iter, gallery_info_to_process_item):
                     data_changed_for_model = True
                     galleries_processed_since_vpn_rotation += 1

                 current_model_galleries_data = data_manager.load_model_galleries_data(model_name_sanitized_iter)
                 data_manager.update_last_model_index(model_idx)
                 reporting.generate_global_html_status()

                 if galleries_processed_since_vpn_rotation >= vpn_rotation_threshold:
                     print(f"🎉 Osiągnięto próg {galleries_processed_since_vpn_rotation} galerii dla rotacji VPN. Restart.");
                     if data_changed_for_model: data_manager.save_model_galleries_data(model_name_sanitized_iter, current_model_galleries_data)
                     raise constants.RestartRequiredError("Osiągnięto próg galerii dla rotacji VPN.")

            if data_changed_for_model:
                data_manager.save_model_galleries_data(model_name_sanitized_iter, current_model_galleries_data)

            data_manager.update_last_model_index(model_idx)
            reporting.generate_global_html_status()

        print(f"\n🎉 === ZAKOŃCZONO PRZETWARZANIE LISTY MODELEK ({check_mode}) === 🎉")

    except constants.RestartRequiredError: raise
    except Exception as e: print(f"💥💥 Błąd krytyczny w handle_process_models: {e}"); traceback.print_exc()
    finally:
        if driver:
            print("🚪 Zamykam przeglądarkę (handle_process_models)...")
            driver.quit()
        reporting.update_current_status("Zakończono/Przerwano przetwarzanie modeli", is_processing=False)
        reporting.generate_global_html_status()


def handle_fill_incomplete():
    reporting.update_current_status("Uzupełnianie niekompletnych")
    entries_to_fill = data_manager.load_incomplete_galleries()
    if not entries_to_fill: print("✅ Brak niekompletnych galerii w pliku."); return

    print(f"\n🔧 Uzupełniam {len(entries_to_fill)} niekompletnych galerii...")
    driver = None
    try:
        driver = driver_utils.create_driver_with_retry()
        for idx, entry_data_item in enumerate(entries_to_fill):
            config_handler.load_config() # <-- Sprawdź config przed każdą galerią w tej pętli
            if data_manager.load_priority_queue():
                print("   ⬆️ Wykryto zadania priorytetowe. Przerywam uzupełnianie niekompletnych."); return

            print(f"\n🔧 Uzupełniam [{idx + 1}/{len(entries_to_fill)}]: '{entry_data_item.get('gallery_title', entry_data_item['url'])}'")
            scraped_info_mock = {'url': entry_data_item['url'], 'title': entry_data_item.get('gallery_title'), 'count': entry_data_item.get('expected')}
            process_single_gallery(driver, entry_data_item['model_name'], scraped_info_mock)
            reporting.generate_global_html_status()

        print("\n✅ Zakończono uzupełnianie niekompletnych galerii.")
    except constants.RestartRequiredError: raise
    except Exception as e: print(f"💥💥 Błąd krytyczny w handle_fill_incomplete: {e}"); traceback.print_exc()
    finally:
        if driver:
            print("🚪 Zamykam przeglądarkę (handle_fill_incomplete)...")
            driver.quit()
        reporting.update_current_status("Zakończono uzupełnianie niekompletnych", is_processing=False)
        reporting.generate_global_html_status()