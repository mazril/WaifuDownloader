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
import constants
import config_handler
import reporting

def kill_chrome_processes(): # ... (bez zmian) ...
    print("🔪 Próba zamknięcia wszystkich procesów Chrome/ChromeDriver...")
    killed_something = False
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe", "/T"], check=False, capture_output=True)
            result_chrome = subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], check=False, capture_output=True)
            killed_something = result_chrome.returncode == 0
        else: # Linux/macOS
            subprocess.run(["pkill", "-f", "chromedriver"], check=False, capture_output=True)
            result_chrome = subprocess.run(["pkill", "-f", "chrome"], check=False, capture_output=True)
            killed_something = result_chrome.returncode == 0

        if killed_something: print("   Pomyślnie wysłano sygnały zamknięcia."); time.sleep(3)
        else: print("   Nie znaleziono procesów lub wystąpił błąd (kontynuuję).")
    except FileNotFoundError: print("   ⚠️ Komenda 'taskkill' / 'pkill' nie znaleziona.")
    except Exception as e: print(f"   ⚠️ Nieoczekiwany błąd podczas zamykania procesów: {e}")

def _create_driver_instance_for_thread(q_result, adblock_path_local):
    try:
        service = ChromeService(log_path=os.devnull)
        options = uc.ChromeOptions()
        options.add_argument(f"--user-agent={random.choice(constants.USER_AGENTS)}")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-infobars")
        options.add_argument("--no-first-run")

        # --- DODANO: Przełączniki wyłączające ograniczanie w tle ---
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        print("   (Wątek) 🔧 Dodano opcje --disable-background-*")
        # --- KONIEC DODANO ---

        if os.path.exists(adblock_path_local):
            print(f"   (Wątek) 🔧 Dodaję AdBlocka: {adblock_path_local}"); options.add_extension(adblock_path_local)
        else: print(f"   (Wątek) ⚠️ Nie znaleziono AdBlocka: {adblock_path_local}")

        print("   (Wątek) 🚀 Uruchamiam uc.Chrome()..."); driver = uc.Chrome(service=service, options=options)
        print("   (Wątek) 🌐 Sprawdzam responsywność..."); _ = driver.current_url
        print("   (Wątek) ✅ Przeglądarka gotowa. Czekam na AdBlocka..."); time.sleep(5)
        q_result.put(driver)
    except Exception as e_thread: q_result.put(e_thread)

def create_driver_with_retry(): # ... (bez zmian) ...
    for attempt in range(1, constants.MAX_DRIVER_STARTUP_ATTEMPTS + 1):
        print(f"\n🚀 Próba uruchomienia przeglądarki ({attempt}/{constants.MAX_DRIVER_STARTUP_ATTEMPTS})...")
        driver = None; thread_result_queue = queue.Queue()
        creation_thread = threading.Thread(target=_create_driver_instance_for_thread, args=(thread_result_queue, constants.ADBLOCK_EXTENSION_PATH))
        creation_thread.daemon = True; creation_thread.start(); creation_thread.join(timeout=constants.DRIVER_STARTUP_TIMEOUT)

        if creation_thread.is_alive():
            print(f"🔴 Timeout ({constants.DRIVER_STARTUP_TIMEOUT}s) (próba {attempt})."); kill_chrome_processes()
            if attempt < constants.MAX_DRIVER_STARTUP_ATTEMPTS: time.sleep(5); continue
            else: raise constants.RestartRequiredError("Nie udało się uruchomić przeglądarki (timeout).")
        else:
            try:
                result = thread_result_queue.get_nowait()
                if isinstance(result, Exception):
                    print(f"   💥 Błąd w wątku (próba {attempt}): {result}"); kill_chrome_processes()
                    if attempt < constants.MAX_DRIVER_STARTUP_ATTEMPTS: time.sleep(5); continue
                    else: raise constants.RestartRequiredError(f"Błąd tworzenia drivera: {result}")
                driver = result; print("✅ Przeglądarka uruchomiona!"); return driver
            except queue.Empty:
                print(f"   ⚠️ Błąd: Pusta kolejka (próba {attempt})."); kill_chrome_processes()
                if attempt < constants.MAX_DRIVER_STARTUP_ATTEMPTS: time.sleep(5); continue
                else: raise constants.RestartRequiredError("Nieznany błąd tworzenia drivera.")
    raise constants.RestartRequiredError("Nie udało się uruchomić przeglądarki.")

def is_blocked(driver): # ... (bez zmian) ...
    try:
        # time.sleep(0.5)  # Usunięto w poprzednim kroku
        title = driver.title.lower()
        block_phrases_title = ['just a moment', 'access denied', 'error 1020', 'error 1009', 'captcha', '403']
        if any(phrase in title for phrase in block_phrases_title):
            print(f"🧱 Blokada (Tytuł: {driver.title})."); return True

        if driver.find_elements(By.CSS_SELECTOR, 'div#g-recaptcha, div.h-captcha, iframe[src*="captcha"], #cf-challenge-running, #challenge-form'):
            print(f"🧱 Blokada (Element CAPTCHA)."); return True

        source = driver.page_source.lower()
        source = re.sub(r'<div class="container mb-1">.*?</div>', '', source, flags=re.DOTALL | re.IGNORECASE)

        if 'checking if the site connection is secure' in source:
            print(f"🧱 Wykryto 'checking...'. Czekam 3s..."); time.sleep(3.0)
            source_new = re.sub(r'<div class="container mb-1">.*?</div>', driver.page_source.lower(), flags=re.DOTALL | re.IGNORECASE)
            if 'checking if the site connection is secure' in source_new or 'just a moment' in driver.title.lower():
                 print(f"   ... Blokada potwierdzona."); return True
            else: print("   ... Prawdopodobnie OK."); return False

        block_phrases_source = ['captcha', 'access denied', 'error 1020', 'error 1009', '403 forbidden']
        if any(phrase in source for phrase in block_phrases_source):
            print(f"🧱 Blokada (Źródło)."); return True

    except WebDriverException as e: print(f"🧱 Błąd WebDrivera (traktuję jak blokadę): {e}"); return True
    except Exception as e: print(f"🧱 Błąd (traktuję jak blokadę): {e}"); return True
    return False

def check_and_handle_block(driver, url_being_loaded="bieżący URL", retries=1, delay=5): # ... (bez zmian) ...
    if is_blocked(driver):
        print(f"🛑 Wykryto blokadę na {url_being_loaded}! Wymagana rotacja IP i restart...")
        try:
            debug_filename = f"block_debug_{time.time():.0f}.html"
            with open(debug_filename, 'w', encoding='utf-8') as f: f.write(driver.page_source)
            print(f"   💾 Zapisano źródło strony do {debug_filename}")
        except Exception as dbg_e: print(f"   ⚠️ Nie udało się zapisać źródła: {dbg_e}")
        raise constants.RestartRequiredError(f"Wykryto blokadę (CAPTCHA/Cloudflare) na {url_being_loaded}.")

def safe_driver_get(driver, url): # ... (bez zmian) ...
    print(f"⏳ Przechodzę do: {url}")
    try:
        driver.get(url)
        time.sleep(random.uniform(4.0, 6.0))
        check_and_handle_block(driver, url)
    except constants.RestartRequiredError: raise
    except WebDriverException as e:
        msg = str(e).lower()
        if any(err in msg for err in ["net::err", "timed out", "reset", "unreachable"]):
            raise constants.RestartRequiredError(f"Błąd sieci '{str(e).splitlines()[0]}' na {url}") from e
        else: raise constants.RestartRequiredError(f"WebDriverException '{str(e).splitlines()[0]}' na {url}") from e
    except Exception as e: raise constants.RestartRequiredError(f"Nieoczekiwany błąd '{str(e).splitlines()[0]}' na {url}") from e


def _is_element_in_viewport(driver, element): # ... (bez zmian) ...
    """Sprawdza, czy element Selenium jest widoczny w oknie przeglądarki."""
    return driver.execute_script("""
        const el = arguments[0];
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        return (
            rect.top >= 0 &&
            rect.left >= 0 &&
            rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
            rect.right <= (window.innerWidth || document.documentElement.clientWidth)
        );
    """, element)

def scroll_until_timeout(driver, selector, expected_count=None, allow_up_scroll=True,
                         gallery_id=None, model_name=None, gallery_title=None,
                         initial_downloaded_count=0,
                         current_expected_count_for_reporting=None): # ... (bez zmian) ...

    config_handler.load_config()
    cfg_initial = config_handler.current_config['scrolling']
    print(f"DEBUG_SUT: Rozpoczynam scroll_until_timeout dla '{gallery_title if gallery_title else 'Nieznana galeria'}'. Oczekiwane (parametr): {expected_count}, Oczekiwane dla raportowania: {current_expected_count_for_reporting}")
    print(f"DEBUG_SUT: Inicjalnie pobranych (parametr): {initial_downloaded_count}")

    check_and_handle_block(driver, driver.current_url)
    last_new_time = time.time(); refresh_count = 0; ymal_detections = 0; scroll_counter = 0
    elems = []
    try:
        elems = driver.find_elements(By.CSS_SELECTOR, selector)
    except WebDriverException as e_find:
        print(f"DEBUG_SUT: Błąd przy początkowym find_elements: {e_find}")
    last_count_on_page = len(elems)
    print(f"DEBUG_SUT: Start: {last_count_on_page} elementów na stronie (selektor: '{selector}').")

    if gallery_id:
        reporting.update_current_status(
            message=f"Szukanie... (Na stronie: {last_count_on_page})", model=model_name, gallery=gallery_title,
            gallery_id=gallery_id, is_processing=True,
            scan_session_found_count=last_count_on_page,
            downloaded_count=initial_downloaded_count,
            expected_count=current_expected_count_for_reporting
        )

    while True:
        config_handler.load_config()
        cfg = config_handler.current_config['scrolling']
        wait_for_new = cfg['wait_for_new']['value']
        pause_between_min = cfg['pause_between_min']['value']
        pause_between_max = cfg['pause_between_max']['value']
        pause_between = random.uniform(pause_between_min, pause_between_max)
        jump_distance = cfg['jump_distance']['value']
        spinner_wait_time = cfg['spinner_wait_time']['value']
        refresh_main = cfg['refresh_jumps_main']['value']
        up_gal = cfg['gallery_up_jumps']['value']
        down_gal = cfg['gallery_down_jumps']['value']
        max_ref = cfg['max_refresh']['value']
        max_ymal = cfg['MAX_YMAL_CONSECUTIVE_CORRECTIONS']['value']

        check_and_handle_block(driver, driver.current_url)
        scroll_counter += 1
        driver.execute_script(f"window.scrollBy(0, {int(jump_distance * random.uniform(0.7, 1.3))});")
        time.sleep(pause_between)

        # --- LOGIKA SPRAWDZANIA SPINNERA (Z WERYFIKACJĄ WIDOCZNOŚCI) ---
        try:
            spinner = driver.find_element(By.ID, "loading-spinner")
            if spinner and spinner.is_displayed() and _is_element_in_viewport(driver, spinner):
                print("DEBUG_SUT: 🍥 Wykryto WIDOCZNY NA EKRANIE spinner ładowania. Czekam...")
                spinner_start_time = time.time()
                while time.time() - spinner_start_time < spinner_wait_time:
                    time.sleep(1.0)
                    try:
                        spinner_now = driver.find_element(By.ID, "loading-spinner")
                        current_elems_list_spinner = driver.find_elements(By.CSS_SELECTOR, selector)
                        if not spinner_now.is_displayed() or not _is_element_in_viewport(driver, spinner_now):
                            print("DEBUG_SUT:   🍥 Spinner zniknął lub jest poza ekranem. Kontynuuję.")
                            last_new_time = time.time()
                            break
                        if len(current_elems_list_spinner) > last_count_on_page:
                            print("DEBUG_SUT:   🍥 Nowe elementy pojawiły się podczas oczekiwania na spinner. Kontynuuję.")
                            last_new_time = time.time()
                            break
                        print(f"DEBUG_SUT:   🍥 Czekam na spinner... ({time.time() - spinner_start_time:.1f}s / {spinner_wait_time}s)")
                    except NoSuchElementException:
                        print("DEBUG_SUT:   🍥 Spinner zniknął (NoSuchElementException). Kontynuuję.")
                        last_new_time = time.time()
                        break
                    except Exception as e_inner:
                        print(f"DEBUG_SUT:   ⚠️ Błąd w pętli spinnera: {e_inner}")
                        break
                else:
                     print(f"DEBUG_SUT:   🍥 Timeout ({spinner_wait_time}s) oczekiwania na spinner. Zdam się na główny timeout.")
        except NoSuchElementException:
            pass
        except Exception as e_spinner:
            print(f"DEBUG_SUT:   ⚠️ Błąd podczas sprawdzania spinnera: {e_spinner}")
        # --- KONIEC LOGIKI SPINNERA ---


        if not allow_up_scroll:
            try:
                ymle = driver.find_elements(By.XPATH, "//h1[contains(., 'YOU MAY ALSO LIKE:')]")
                if ymle and ymle[0].is_displayed() and ymle[0].location['y'] < driver.execute_script("return window.pageYOffset + window.innerHeight * 0.7;"):
                    ymal_detections += 1
                    if ymal_detections <= max_ymal:
                        print(f"⚠️ YMAL ({ymal_detections}/{max_ymal}). Koryguję...");
                        for _ in range(up_gal): driver.execute_script(f"window.scrollBy(0, -{jump_distance});"); time.sleep(0.3)
                        last_new_time = time.time(); continue
                    else: print("⚠️ YMAL: Zdam się na timeout.")
            except Exception: pass

        current_elems_list = []
        try:
            current_elems_list = driver.find_elements(By.CSS_SELECTOR, selector)
        except WebDriverException as e_find_loop:
            print(f"DEBUG_SUT: Błąd find_elements w pętli: {e_find_loop}")
        current_found_on_page = len(current_elems_list)

        if current_found_on_page > last_count_on_page:
            print(f"DEBUG_SUT: ➕ {current_found_on_page - last_count_on_page} nowych (łącznie na stronie: {current_found_on_page})")
            last_count_on_page = current_found_on_page
            last_new_time = time.time()
            elems = current_elems_list
            ymal_detections = 0
            if gallery_id:
                reporting.update_current_status(
                    message=f"Szukanie... (Na stronie: {current_found_on_page})", model=model_name, gallery=gallery_title,
                    gallery_id=gallery_id, is_processing=True,
                    scan_session_found_count=current_found_on_page,
                    downloaded_count=initial_downloaded_count,
                    expected_count=current_expected_count_for_reporting
                )

        elapsed = time.time() - last_new_time
        print(f"DEBUG_SUT: ⏳ {elapsed:.1f}s (na stronie: {current_found_on_page}, oczekiwane do znalezienia na stronie: {expected_count or 'brak limitu'}, timeout: {wait_for_new}s)")

        if expected_count is not None and current_found_on_page >= expected_count:
            print(f"DEBUG_SUT: ✅ Znaleziono wymaganą liczbę ({current_found_on_page}/{expected_count}) lub więcej elementów na stronie.")
            break
        if elapsed < wait_for_new:
            continue

        print(f"DEBUG_SUT: Timeout ({elapsed:.1f}s >= {wait_for_new}s). Próba odświeżenia #{refresh_count + 1}")
        if refresh_count < max_ref:
            refresh_count += 1; print(f"🔄 Timeout! Odświeżam (#{refresh_count})...");
            up, down = (refresh_main, refresh_main) if allow_up_scroll else (up_gal, down_gal)
            for _ in range(up): driver.execute_script(f"window.scrollBy(0, -{jump_distance});"); time.sleep(0.3)
            time.sleep(1.5)
            for _ in range(down): driver.execute_script(f"window.scrollBy(0, {jump_distance});"); time.sleep(0.3)
            last_new_time = time.time(); ymal_detections = 0
        else:
            print(f"DEBUG_SUT: 🛑 Max odświeżeń ({current_found_on_page}/{expected_count or '?'}). Zakończono scrollowanie.")
            break
    print(f"DEBUG_SUT: Zakończono scroll_until_timeout. Zwracam {len(elems)} elementów.")
    return elems