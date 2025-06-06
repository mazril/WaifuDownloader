# start.py
import subprocess
import time
import sys
import os
import logging
import requests # Do sprawdzania Ollamy

# --- Konfiguracja loggingu dla start.py ---
log_formatter_start = logging.Formatter('%(asctime)s [%(levelname)-8s] [START_PY:%(lineno)4d] %(message)s')
console_handler_start = logging.StreamHandler(sys.stdout)
console_handler_start.setFormatter(log_formatter_start)
logger_start = logging.getLogger("start_py")
logger_start.addHandler(console_handler_start)
logger_start.setLevel(logging.INFO)

# Importuj ścieżki i konfiguracje z constants i config_handler
try:
    import constants
    import config_handler
    config_handler.load_config(force_reload=True) 
except ImportError as e:
    logger_start.error(f"Nie można zaimportować constants lub config_handler: {e}. Upewnij się, że są w PYTHONPATH.")
    sys.exit(1)
except Exception as e_cfg:
    logger_start.error(f"Błąd podczas ładowania konfiguracji w start.py: {e_cfg}")
    sys.exit(1)


OLLAMA_COMMAND = "ollama serve" 
PYTHON_EXECUTABLE = sys.executable 

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_PY_SCRIPT = os.path.join(SCRIPT_DIR, "main.py")
TESTAI_WORKER_PY_SCRIPT = os.path.join(SCRIPT_DIR, "testai_worker.py")

def is_ollama_server_running():
    """
    Sprawdza, czy serwer Ollama odpowiada, używając adresu z config.json.
    Opis: Modyfikacja polega na odczytaniu adresu URL serwera Ollama z konfiguracji, 
          zamiast używać stałej.
    Wpływ na inne funkcje: Umożliwia dynamiczną zmianę adresu serwera Ollama.
    """
    config_handler.load_config()
    ollama_base_url = config_handler.current_config['ai_settings']['api_base_url']['value']
    
    try:
        response = requests.head(ollama_base_url, timeout=3)
        if response.status_code == 200 or response.status_code == 404: 
            try:
                response_tags = requests.get(f"{ollama_base_url}/api/tags", timeout=3)
                if response_tags.status_code == 200:
                    logger_start.debug("Serwer Ollama odpowiada na /api/tags.")
                    return True
                else:
                    logger_start.warning(f"Serwer Ollama na {ollama_base_url} odpowiedział statusem {response_tags.status_code} na /api/tags.")
                    return False
            except requests.exceptions.RequestException:
                logger_start.warning(f"Serwer Ollama na {ollama_base_url} nie odpowiedział na /api/tags (RequestException).")
                return False
        logger_start.warning(f"Serwer Ollama na {ollama_base_url} odpowiedział statusem {response.status_code} na HEAD /.")
        return False
    except requests.exceptions.ConnectionError:
        logger_start.info(f"Serwer Ollama na {ollama_base_url} nie jest dostępny (ConnectionError).")
        return False
    except requests.exceptions.Timeout:
        logger_start.info(f"Timeout podczas sprawdzania serwera Ollama na {ollama_base_url}.")
        return False
    except Exception as e:
        logger_start.error(f"Nieoczekiwany błąd podczas sprawdzania serwera Ollama: {e}")
        return False

def start_ollama_server_subprocess():
    """Próbuje uruchomić serwer Ollama jako podproces."""
    if is_ollama_server_running():
        logger_start.info("Serwer Ollama już działa.")
        return None 

    logger_start.info(f"Próba uruchomienia serwera Ollama poleceniem: {OLLAMA_COMMAND}")
    try:
        if sys.platform == "win32":
            process = subprocess.Popen(OLLAMA_COMMAND, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            process = subprocess.Popen(OLLAMA_COMMAND, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        
        logger_start.info(f"Polecenie uruchomienia Ollamy wysłane (PID: {process.pid if process and hasattr(process, 'pid') else 'nieznany'}). Czekam chwilę na start...")
        time.sleep(10) 
        
        if is_ollama_server_running():
            logger_start.info("Serwer Ollama został pomyślnie uruchomiony przez start.py.")
            return process
        else:
            logger_start.error("Nie udało się potwierdzić uruchomienia serwera Ollama po wysłaniu polecenia.")
            if process and hasattr(process, 'pid') and process.poll() is None:
                logger_start.info(f"Próbuję zakończyć proces Ollama (PID: {process.pid}), który mógł się zawiesić przy starcie.")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            return None
    except FileNotFoundError:
        logger_start.error(f"Nie znaleziono polecenia '{OLLAMA_COMMAND.split()[0]}'. Upewnij się, że Ollama jest zainstalowana i w PATH.")
        return None
    except Exception as e:
        logger_start.error(f"Błąd podczas próby uruchomienia serwera Ollama: {e}")
        return None

def run_script(script_path, name):
    """
    Uruchamia dany skrypt Pythona jako podproces w nowym oknie konsoli.
    Opis: Bez zmian w tej funkcji.
    """
    logger_start.info(f"Uruchamiam skrypt: {name} ({script_path}) w nowym oknie...")
    cmd = [PYTHON_EXECUTABLE, script_path]
    process = None
    try:
        if sys.platform == "win32":
            process = subprocess.Popen(cmd, cwd=SCRIPT_DIR, creationflags=subprocess.CREATE_NEW_CONSOLE)
        elif sys.platform == "darwin": # macOS
            script_content = f'tell application "Terminal" to do script "{PYTHON_EXECUTABLE} \\"{script_path}\\" in window 1'
            process = subprocess.Popen(['osascript', '-e', script_content], cwd=SCRIPT_DIR)
        elif sys.platform.startswith("linux"):
            try:
                process = subprocess.Popen(['gnome-terminal', '--', PYTHON_EXECUTABLE, script_path], cwd=SCRIPT_DIR)
                logger_start.info(f"Uruchomiono {name} w gnome-terminal.")
            except FileNotFoundError:
                logger_start.warning("Nie znaleziono gnome-terminal. Próbuję z xterm...")
                try:
                    process = subprocess.Popen(['xterm', '-hold', '-e', PYTHON_EXECUTABLE, script_path], cwd=SCRIPT_DIR)
                    logger_start.info(f"Uruchomiono {name} w xterm.")
                except FileNotFoundError:
                    logger_start.error("Nie znaleziono gnome-terminal ani xterm. Uruchamiam skrypt w bieżącej konsoli.")
                    process = subprocess.Popen(cmd, cwd=SCRIPT_DIR) # Fallback do bieżącej konsoli
            except Exception as e_linux_term:
                logger_start.error(f"Błąd uruchamiania w nowym terminalu Linux ({e_linux_term}). Uruchamiam w bieżącej konsoli.")
                process = subprocess.Popen(cmd, cwd=SCRIPT_DIR) # Fallback
        else: # Inne systemy
            logger_start.warning(f"Nieznany system operacyjny ({sys.platform}). Uruchamiam skrypt w bieżącej konsoli.")
            process = subprocess.Popen(cmd, cwd=SCRIPT_DIR)
        
        if process and hasattr(process, 'pid'):
            logger_start.info(f"Skrypt {name} uruchomiony (PID: {process.pid}).")
        elif process:
            logger_start.info(f"Polecenie uruchomienia {name} wysłane.")
        else:
            logger_start.error(f"Nie udało się utworzyć procesu dla {name}.")
        return process
        
    except Exception as e:
        logger_start.error(f"Nie udało się uruchomić skryptu {name}: {e}")
        return None

if __name__ == "__main__":
    logger_start.info("--- Menedżer uruchomieniowy WaifuDownloader ---")

    ollama_process = None
    main_py_process = None
    testai_worker_process = None

    try:
        # 1. Uruchom Ollamę, jeśli nie działa
        ollama_process = start_ollama_server_subprocess()
        if not is_ollama_server_running():
            logger_start.error("Serwer Ollama nie działa i nie udało się go uruchomić. Worker AI może nie działać poprawnie.")

        # 2. Uruchom main.py
        if os.path.exists(MAIN_PY_SCRIPT):
            main_py_process = run_script(MAIN_PY_SCRIPT, "main.py")
        else:
            logger_start.error(f"Nie znaleziono skryptu {MAIN_PY_SCRIPT}. Nie można uruchomić głównego procesu pobierania.")

        # 3. Uruchom testai_worker.py
        if os.path.exists(TESTAI_WORKER_PY_SCRIPT):
            testai_worker_process = run_script(TESTAI_WORKER_PY_SCRIPT, "testai_worker.py")
        else:
            logger_start.error(f"Nie znaleziono skryptu {TESTAI_WORKER_PY_SCRIPT}. Nie można uruchomić workera AI.")
        
        logger_start.info("Wszystkie docelowe procesy zostały uruchomione (lub podjęto próbę). Menedżer pozostaje aktywny.")
        logger_start.info("Logi z main.py i testai_worker.py będą widoczne w ich dedykowanych oknach konsoli (jeśli system na to pozwolił).")
        logger_start.info("Aby zatrzymać wszystkie procesy, zamknij to okno menedżera (Ctrl+C).")

        while True:
            time.sleep(10)
            
            if main_py_process and main_py_process.poll() is not None:
                logger_start.warning(f"Proces main.py (PID: {main_py_process.pid if hasattr(main_py_process, 'pid') else 'N/A'}) zakończył się z kodem {main_py_process.returncode}. Próba restartu...")
                main_py_process = run_script(MAIN_PY_SCRIPT, "main.py")
            elif not main_py_process and os.path.exists(MAIN_PY_SCRIPT):
                logger_start.warning(f"Proces main.py nie został poprawnie uruchomiony. Ponowna próba...")
                main_py_process = run_script(MAIN_PY_SCRIPT, "main.py")

            if testai_worker_process and testai_worker_process.poll() is not None:
                logger_start.warning(f"Proces testai_worker.py (PID: {testai_worker_process.pid if hasattr(testai_worker_process, 'pid') else 'N/A'}) zakończył się z kodem {testai_worker_process.returncode}. Próba restartu...")
                testai_worker_process = run_script(TESTAI_WORKER_PY_SCRIPT, "testai_worker.py")
            elif not testai_worker_process and os.path.exists(TESTAI_WORKER_PY_SCRIPT):
                 logger_start.warning(f"Proces testai_worker.py nie został poprawnie uruchomiony. Ponowna próba...")
                 testai_worker_process = run_script(TESTAI_WORKER_PY_SCRIPT, "testai_worker.py")

            if ollama_process and ollama_process.poll() is not None: 
                 logger_start.warning("Serwer Ollama (uruchomiony przez start.py) przestał działać. Próba ponownego uruchomienia...")
                 ollama_process = start_ollama_server_subprocess()
            elif not is_ollama_server_running() and ollama_process is None:
                 logger_start.warning("Zewnętrzny serwer Ollama przestał odpowiadać. Sprawdź jego status.")

    except KeyboardInterrupt:
        logger_start.info("Otrzymano Ctrl+C. Zamykanie podprocesów...")
    except Exception as e:
        logger_start.error(f"Nieoczekiwany błąd w start.py: {e}", exc_info=True)
    finally:
        logger_start.info("Kończenie pracy menedżera...")
        processes_to_terminate = []
        if testai_worker_process and hasattr(testai_worker_process, 'pid') and testai_worker_process.poll() is None:
            processes_to_terminate.append(("testai_worker.py", testai_worker_process))
        
        if main_py_process and hasattr(main_py_process, 'pid') and main_py_process.poll() is None:
            processes_to_terminate.append(("main.py", main_py_process))

        for name, proc in processes_to_terminate:
            logger_start.info(f"Zatrzymywanie {name} (PID: {proc.pid})...")
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger_start.warning(f"Timeout podczas zamykania {name} (PID: {proc.pid}). Wymuszam (kill)...")
                proc.kill()
            except Exception as e_term:
                logger_start.error(f"Błąd podczas zamykania {name} (PID: {proc.pid}): {e_term}")

        if ollama_process and hasattr(ollama_process, 'pid') and ollama_process.poll() is None: 
            logger_start.info(f"Zatrzymywanie serwera Ollama (PID: {ollama_process.pid}) uruchomionego przez start.py...")
            try:
                ollama_process.terminate()
                ollama_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ollama_process.kill()
            except Exception as e_term_ollama:
                logger_start.error(f"Błąd podczas zamykania Ollamy: {e_term_ollama}")
        
        logger_start.info("Menedżer zakończył działanie.")