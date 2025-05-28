# -*- coding: utf-8 -*-
import os
import sys
import time
import random
import re
import subprocess
import threading
import queue
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import WebDriverException, NoSuchElementException
import logging

import constants
import config_handler
import reporting
import main # Dla main.shutdown_requested

logger = logging.getLogger(__name__)

def kill_chrome_processes():
    logger.info("Próba zamknięcia wszystkich procesów Chrome/ChromeDriver...")
    killed_something = False
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe", "/T"], check=False, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            result_chrome = subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], check=False, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            killed_something = result_chrome.returncode == 0
        else:
            subprocess.run(["pkill", "-f", "chromedriver"], check=False, capture_output=True)
            result_chrome = subprocess.run(["pkill", "-f", "chrome"], check=False, capture_output=True)
            killed_something = result_chrome.returncode == 0

        if killed_something:
            logger.info("Pomyślnie wysłano sygnały zamknięcia dla Chrome/ChromeDriver.")
            time.sleep(3) 
        else:
            logger.info("Nie znaleziono procesów Chrome/ChromeDriver do zamknięcia lub wystąpił błąd (kontynuuję).")
    except FileNotFoundError:
        logger.warning("Komenda 'taskkill' / 'pkill' nie znaleziona w systemie.")
    except Exception as e:
        logger.warning(f"Nieoczekiwany błąd podczas zamykania procesów Chrome/ChromeDriver: {e}", exc_info=False)

def _create_driver_instance_for_thread(q_result, adblock_path_local):
    logger.debug(f"Rozpoczynam tworzenie instancji drivera w wątku (AdBlock: {adblock_path_local})")
    adblock_loaded_successfully = False
    try:
        service = ChromeService(log_path=os.devnull)
        options = uc.ChromeOptions()
        options.add_argument(f"--user-agent={random.choice(constants.USER_AGENTS)}")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-infobars")
        options.add_argument("--no-first-run")
        
        # === OPCJE WYŁĄCZAJĄCE OSZCZĘDZANIE ENERGII W TLE ===
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        # Dodatkowe, które mogą pomóc:
        options.add_argument("--disable-features=VisibilityAwarePageOcclusion") 
        if sys.platform == "win32": # Tylko dla Windows
            options.add_argument("--disable-features=CalculateNativeWinOcclusion")
        logger.info("Dodano opcje Chrome: --disable-background-*, --disable-features=VisibilityAwarePageOcclusion itp.")
        # =====================================================

        if os.path.exists(adblock_path_local):
            logger.info(f"Dodaję rozszerzenie AdBlock z: {adblock_path_local}")
            options.add_extension(adblock_path_local)
            adblock_loaded_successfully = True
        else:
            logger.warning(f"Nie znaleziono rozszerzenia AdBlock w: {adblock_path_local}")

        logger.info("Uruchamiam uc.Chrome()...")
        driver = uc.Chrome(service=service, options=options)
        logger.info("Instancja uc.Chrome() uruchomiona. Sprawdzam responsywność...")
        _ = driver.current_url 
        logger.info("Przeglądarka responsywna.")

        if adblock_loaded_successfully:
            logger.info("Czekam na załadowanie AdBlocka (5s)...")
            time.sleep(5)
        else:
            logger.debug("AdBlock niezaładowany, krótka pauza (2s).")
            time.sleep(2)

        logger.info("Przeglądarka gotowa.")
        q_result.put(driver)
    except Exception as e_thread:
        logger.error(f"Błąd w wątku tworzenia drivera: {e_thread}", exc_info=True)
        q_result.put(e_thread)


def create_driver_with_retry():
    for attempt in range(1, constants.MAX_DRIVER_STARTUP_ATTEMPTS + 1):
        logger.info(f"Próba uruchomienia przeglądarki ({attempt}/{constants.MAX_DRIVER_STARTUP_ATTEMPTS})...")
        if attempt > 1: 
             kill_chrome_processes()
             time.sleep(2) 

        driver = None
        thread_result_queue = queue.Queue()

        creation_thread = threading.Thread(
            target=_create_driver_instance_for_thread,
            args=(thread_result_queue, constants.ADBLOCK_EXTENSION_PATH)
        )
        creation_thread.daemon = True
        creation_thread.start()
        creation_thread.join(timeout=constants.DRIVER_STARTUP_TIMEOUT)

        if creation_thread.is_alive():
            logger.error(f"Timeout ({constants.DRIVER_STARTUP_TIMEOUT}s) podczas uruchamiania przeglądarki (próba {attempt}).")
            if attempt >= constants.MAX_DRIVER_STARTUP_ATTEMPTS:
                raise constants.RestartRequiredError("Nie udało się uruchomić przeglądarki (timeout po wielu próbach).")
        else:
            try:
                result = thread_result_queue.get_nowait()
                if isinstance(result, Exception):
                    logger.error(f"Błąd w wątku tworzenia drivera (próba {attempt}): {result}", exc_info=False)
                    if attempt >= constants.MAX_DRIVER_STARTUP_ATTEMPTS:
                        raise constants.RestartRequiredError(f"Błąd tworzenia drivera po wielu próbach: {result}")
                else:
                    logger.info("Przeglądarka uruchomiona pomyślnie!")
                    return result
            except queue.Empty:
                logger.error(f"Błąd: Pusta kolejka po zakończeniu wątku tworzenia drivera (próba {attempt}).")
                if attempt >= constants.MAX_DRIVER_STARTUP_ATTEMPTS:
                    raise constants.RestartRequiredError("Nieznany błąd tworzenia drivera (pusta kolejka).")
        
        logger.info("Czekam 5s przed następną próbą...")
        time.sleep(5)

    raise constants.RestartRequiredError("Nie udało się uruchomić przeglądarki po wszystkich próbach.")


def is_driver_responsive(driver):
    if driver is None: return False
    try: _ = driver.current_url; return True
    except WebDriverException: logger.warning("Driver nie odpowiada (WebDriverException)."); return False
    except Exception as e: logger.warning(f"Driver nie odpowiada (Inny błąd: {e})."); return False

def is_blocked(driver):
    try:
        title = driver.title.lower()
        block_phrases_title = ['just a moment', 'access denied', 'error 1020', 'error 1009', 'captcha', '403 forbidden', 'attention required']
        if any(phrase in title for phrase in block_phrases_title):
            logger.warning(f"Wykryto blokadę (Tytuł strony: '{driver.title}').")
            return True

        if driver.find_elements(By.CSS_SELECTOR, 'div#g-recaptcha, div.h-captcha, iframe[src*="captcha"], #cf-challenge-running, #challenge-form, form#challenge-form'):
            logger.warning("Wykryto blokadę (Element CAPTCHA na stronie).")
            return True

        source = driver.page_source.lower()
        source_cleaned = re.sub(r'<div class="container mb-1">.*?</div>', '', source, flags=re.DOTALL | re.IGNORECASE)

        if 'checking if the site connection is secure' in source_cleaned or 'verify you are human' in source_cleaned:
            logger.info("Wykryto komunikat 'checking...' lub 'verify...'. Czekam do 5s na rozwiązanie...")
            time.sleep(5.0)
            title_after_wait = driver.title.lower()
            source_after_wait = driver.page_source.lower()
            if 'checking if the site connection is secure' in source_after_wait or \
               'verify you are human' in source_after_wait or \
               any(phrase in title_after_wait for phrase in block_phrases_title):
                 logger.warning("Blokada 'checking/verify...' potwierdzona po oczekiwaniu.")
                 return True
            else:
                 logger.info("Komunikat 'checking/verify...' prawdopodobnie zniknął.")
                 return False

        block_phrases_source = ['captcha', 'access denied', 'error 1020', 'error 1009', '403 forbidden']
        if any(phrase in source_cleaned for phrase in block_phrases_source):
            logger.warning("Wykryto blokadę (Słowo kluczowe w źródle strony).")
            return True

    except WebDriverException as e:
        logger.warning(f"Błąd WebDrivera podczas sprawdzania blokady (traktuję jak blokadę): {e}", exc_info=False)
        return True
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd podczas sprawdzania blokady (traktuję jak blokadę): {e}", exc_info=True)
        return True
    return False

def check_and_handle_block(driver, url_being_loaded="bieżący URL"):
    if is_blocked(driver):
        logger.critical(f"Wykryto blokadę na {url_being_loaded}! Wymagana rotacja IP i restart...")
        try:
            timestamp_str = time.strftime("%Y%m%d_%H%M%S")
            debug_dir = os.path.join(constants.SCRIPT_DIR, "debug_screens")
            os.makedirs(debug_dir, exist_ok=True)
            sanitized_url_part = re.sub(r'[^a-zA-Z0-9_-]', '_', url_being_loaded.split('/')[-1])[:50]
            base_filename = f"block_debug_{sanitized_url_part}_{timestamp_str}"
            debug_filename_html = os.path.join(debug_dir, f"{base_filename}.html")
            debug_filename_png = os.path.join(debug_dir, f"{base_filename}.png")
            with open(debug_filename_html, 'w', encoding='utf-8') as f: f.write(driver.page_source)
            driver.save_screenshot(debug_filename_png)
            logger.info(f"Zapisano źródło strony do {debug_filename_html} i zrzut ekranu do {debug_filename_png}")
        except Exception as dbg_e: logger.warning(f"Nie udało się zapisać plików debugowania blokady: {dbg_e}", exc_info=False)
        raise constants.RestartRequiredError(f"Wykryto blokadę (CAPTCHA/Cloudflare) na {url_being_loaded}.")

def safe_driver_get(driver, url):
    logger.info(f"Przechodzę do: {url}")
    try:
        driver.get(url)
        pause = random.uniform(3.5, 6.0) 
        logger.debug(f"Pauza po driver.get: {pause:.2f}s")
        time.sleep(pause)
        check_and_handle_block(driver, url)
    except constants.RestartRequiredError: raise
    except WebDriverException as e:
        msg = str(e).lower(); msg_short = str(e).splitlines()[0]
        if any(err in msg for err in ["net::err", "timed out", "timeout", "reset", "unreachable", "dns_probe_finished_no_internet"]):
            raise constants.RestartRequiredError(f"Błąd sieci '{msg_short}' na {url}", no_vpn=True) from e
        else: raise constants.RestartRequiredError(f"WebDriverException '{msg_short}' na {url}") from e
    except Exception as e: raise constants.RestartRequiredError(f"Nieoczekiwany błąd '{str(e).splitlines()[0]}' na {url}") from e


def _is_element_in_viewport(driver, element):
    return driver.execute_script("""
        const el = arguments[0];
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        const windowHeight = (window.innerHeight || document.documentElement.clientHeight);
        const windowWidth = (window.innerWidth || document.documentElement.clientWidth);
        const vertInView = (rect.top <= windowHeight) && ((rect.top + rect.height) >= 0);
        const horInView = (rect.left <= windowWidth) && ((rect.left + rect.width) >= 0);
        return (vertInView && horInView);
    """, element)

def scroll_until_timeout(driver, selector, expected_count=None, allow_up_scroll=True,
                         gallery_id=None, model_name=None, gallery_title=None,
                         initial_downloaded_count=0,
                         current_expected_count_for_reporting=None):
    config_handler.load_config()
    cfg = config_handler.current_config['scrolling']
    logger.info(f"SUT: Start dla '{selector}'. Oczekiwane: {expected_count or 'brak'}. Tytuł: '{gallery_title or 'N/A'}'")

    elems = []
    try: elems = driver.find_elements(By.CSS_SELECTOR, selector)
    except WebDriverException as e: logger.warning(f"SUT: Błąd przy początkowym find_elements: {e}", exc_info=False)
    
    last_count_on_page = len(elems)
    last_new_time = time.time()
    refresh_count = 0
    ymal_consecutive_detections = 0 
    scroll_counter = 0

    if gallery_id:
        reporting.update_current_status(
            message=f"Szukanie... ({last_count_on_page})", model=model_name, gallery=gallery_title,
            gallery_id=gallery_id, is_processing=True, scan_session_found_count=last_count_on_page,
            downloaded_count=initial_downloaded_count, expected_count=current_expected_count_for_reporting
        )

    while True:
        if main.shutdown_requested: logger.info("SUT: Żądanie zamknięcia. Przerywam."); break

        if config_handler.load_config(): logger.info("SUT: Konfiguracja przeładowana.")
        cfg = config_handler.current_config['scrolling']
        wait_for_new, p_min, p_max, jump = cfg['wait_for_new']['value'], cfg['pause_between_min']['value'], cfg['pause_between_max']['value'], cfg['jump_distance']['value']
        spinner_wait, r_jumps, up_j, down_j, max_r, max_ymal_corr = cfg['spinner_wait_time']['value'], cfg['refresh_jumps_main']['value'], cfg['gallery_up_jumps']['value'], cfg['gallery_down_jumps']['value'], cfg['max_refresh']['value'], cfg['MAX_YMAL_CONSECUTIVE_CORRECTIONS']['value']

        check_and_handle_block(driver, driver.current_url)
        scroll_counter += 1
        effective_jump = int(jump * random.uniform(0.85, 1.15)) 
        logger.debug(f"SUT Scroll #{scroll_counter}: +{effective_jump}px.")
        driver.execute_script(f"window.scrollBy(0, {effective_jump});")
        time.sleep(random.uniform(p_min, p_max)) 

        try:
            spinner = driver.find_element(By.ID, "loading-spinner") 
            if spinner and spinner.is_displayed() and _is_element_in_viewport(driver, spinner):
                logger.info(f"SUT: 🍥 Wykryto WIDOCZNY spinner. Czekam do {spinner_wait}s...")
                spinner_start = time.time()
                while time.time() - spinner_start < spinner_wait:
                    if main.shutdown_requested: break
                    time.sleep(0.5) 
                    try:
                        spinner_now = driver.find_element(By.ID, "loading-spinner")
                        if not spinner_now.is_displayed() or not _is_element_in_viewport(driver, spinner_now):
                            logger.info("SUT:   🍥 Spinner zniknął lub jest poza ekranem. Kontynuuję."); last_new_time = time.time(); break
                    except NoSuchElementException: logger.info("SUT:   🍥 Spinner zniknął (NSE). Kontynuuję."); last_new_time = time.time(); break
                else: logger.info(f"SUT:   🍥 Timeout ({spinner_wait}s) czekania na spinner. Kontynuuję.")
        except NoSuchElementException: pass 
        except Exception as e: logger.warning(f"SUT:   ⚠️ Błąd spinnera: {e}", exc_info=False)
        if main.shutdown_requested: break

        if not allow_up_scroll:
            try:
                ymal_header_elements = driver.find_elements(By.XPATH, "//h1[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'you may also like:')]")
                if ymal_header_elements and ymal_header_elements[0].is_displayed():
                    ymal_element = ymal_header_elements[0]
                    ymal_y_position = ymal_element.location['y']
                    viewport_upper_half_end_px = driver.execute_script("return window.pageYOffset + window.innerHeight * 0.5;")

                    if ymal_y_position < viewport_upper_half_end_px: 
                        ymal_consecutive_detections += 1
                        logger.warning(f"SUT: ⚠️ YMAL w GÓRNEJ POŁOWIE EKRANU ({ymal_consecutive_detections}/{max_ymal_corr}).")
                        if ymal_consecutive_detections <= max_ymal_corr:
                            logger.info("SUT:     Koryguję pozycję: znaczny scroll w górę, potem skoki góra/dół.")
                            driver.execute_script(f"window.scrollBy(0, -{int(jump * 1.5)});"); time.sleep(0.3)
                            logger.debug(f"SUT:     Skoki GÓRA ({up_j}x -{jump // 2}px)")
                            for _ in range(up_j):
                                if main.shutdown_requested: break
                                driver.execute_script(f"window.scrollBy(0, -{jump // 2});"); time.sleep(0.2)
                            if main.shutdown_requested: break
                            logger.debug(f"SUT:     Skoki DÓŁ ({down_j}x +{jump // 2}px)")
                            for _ in range(down_j):
                                if main.shutdown_requested: break
                                driver.execute_script(f"window.scrollBy(0, {jump // 2});"); time.sleep(0.2)
                            if main.shutdown_requested: break
                            last_new_time = time.time(); continue 
                        else: logger.warning(f"SUT: ⚠️ Osiągnięto limit ({max_ymal_corr}) korekt YMAL. Kończę."); break
                    else: ymal_consecutive_detections = 0 
                else: ymal_consecutive_detections = 0
            except Exception as e_ymal: logger.debug(f"SUT: Błąd YMAL: {e_ymal}", exc_info=False)
        else: ymal_consecutive_detections = 0 
        if main.shutdown_requested: break
        
        current_elems_list = []
        try: current_elems_list = driver.find_elements(By.CSS_SELECTOR, selector)
        except WebDriverException as e: logger.warning(f"SUT: Błąd find_elements w pętli: {e}", exc_info=False)
        
        current_found = len(current_elems_list)
        if current_found > last_count_on_page:
            logger.info(f"SUT: ➕ Znaleziono {current_found - last_count_on_page} nowych (łącznie: {current_found}).")
            last_count_on_page = current_found; last_new_time = time.time(); elems = current_elems_list
            ymal_consecutive_detections = 0 
            if gallery_id: reporting.update_current_status(message=f"Szukanie... ({current_found})", model=model_name, gallery=gallery_title, gallery_id=gallery_id, is_processing=True, scan_session_found_count=current_found, downloaded_count=initial_downloaded_count, expected_count=current_expected_count_for_reporting)

        elapsed = time.time() - last_new_time
        logger.debug(f"SUT: ⏳ Czas bez nowości: {elapsed:.1f}s (limit: {wait_for_new}s). Znaleziono: {current_found}/{expected_count or '?'}.")

        if expected_count is not None and current_found >= expected_count:
            logger.info(f"SUT: ✅ Znaleziono wymaganą liczbę ({current_found}/{expected_count}). Kończę.")
            if len(current_elems_list) > len(elems): elems = current_elems_list
            break
        if elapsed < wait_for_new: continue

        if refresh_count < max_r:
            refresh_count += 1
            logger.info(f"SUT: 🔄 Timeout! Odświeżam pozycję (#{refresh_count}/{max_r})...")
            up_r, down_r = (r_jumps, r_jumps) if allow_up_scroll else (up_j, down_j)
            logger.debug(f"SUT:   Odświeżanie GÓRA ({up_r}x -{jump}px)")
            for _ in range(up_r): driver.execute_script(f"window.scrollBy(0, -{jump});"); time.sleep(0.3)
            time.sleep(random.uniform(0.8, 1.5))
            logger.debug(f"SUT:   Odświeżanie DÓŁ ({down_r}x +{jump}px)")
            for _ in range(down_r): driver.execute_script(f"window.scrollBy(0, {jump});"); time.sleep(0.3)
            last_new_time = time.time(); ymal_consecutive_detections = 0
        else:
            logger.warning(f"SUT: 🛑 Max odświeżeń. Kończę. Znaleziono {current_found}/{expected_count or '?'}.")
            if len(current_elems_list) > len(elems): elems = current_elems_list
            break

    logger.info(f"SUT: Zakończono. Zwracam {len(elems)} elementów.")
    return elems