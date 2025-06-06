# config_handler.py
import os
import json
import time
import logging

logger = logging.getLogger(__name__)

current_config = None
last_config_mtime = 0.0

SCRIPT_DIR_CONFIG = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILENAME_CONST = "config.json" #
CONFIG_FILE_PATH_CONST = os.path.join(SCRIPT_DIR_CONFIG, CONFIG_FILENAME_CONST)


def get_default_config():
    """
    Zwraca domyślną strukturę konfiguracji.
    
    Opis modyfikacji:
    - Zmieniono nazwę klucza `incomplete_gallery_completion_tolerance` na
      `completion_tolerance_percent` w sekcji `downloading`.
    - Zaktualizowano domyślną wartość na 95.0 i opis, aby odzwierciedlał,
      że jest to próg procentowy.
      
    Wpływ na inne funkcje:
    - Ta zmiana wymaga aktualizacji logiki w `processing.py`, która odczytuje
      tę wartość do ustalania statusu `completed_with_tolerance`.
    """
    return {
        "scrolling": {
            "wait_for_new": {"value": 10.0, "description": "Czas (s) oczekiwania na nowe elementy podczas przewijania."},
            "pause_between_min": {"value": 0.2, "description": "Minimalna pauza (s) pomiędzy kolejnymi 'skokami' przewijania."},
            "pause_between_max": {"value": 0.3, "description": "Maksymalna pauza (s) pomiędzy kolejnymi 'skokami' przewijania."},
            "jump_distance": {"value": 500, "description": "Odległość przewijania (px)."},
            "spinner_wait_time": {"value": 15.0, "description": "Max. czas (s) oczekiwania, gdy widoczny jest spinner ładowania."},
            "refresh_jumps_main": {"value": 5, "description": "Skoki góra/dół przy odświeżaniu na stronie modelu."},
            "gallery_up_jumps": {"value": 5, "description": "Skoki w górę przy odświeżaniu w galerii."},
            "gallery_down_jumps": {"value": 3, "description": "Skoki w dół przy odświeżaniu w galerii."},
            "max_refresh": {"value": 1, "description": "Max. prób odświeżenia przewijania."},
            "MAX_YMAL_CONSECUTIVE_CORRECTIONS": {"value": 4, "description": "Max. korekt dla sekcji 'YOU MAY ALSO LIKE:'."}
        },
        "downloading": {
            "download_delay_min": {"value": 0.8, "description": "Min. czas (s) oczekiwania przed pobraniem obrazka."},
            "download_delay_max": {"value": 1.6, "description": "Max. czas (s) oczekiwania przed pobraniem obrazka."},
            "completion_tolerance_percent": {"value": 95.0, "description": "Procent pobranych plików (np. 95), przy którym galeria jest uznawana za 'ukończoną z tolerancją'."}
        },
        "pauses_and_rotation": {
            "gallery_pause": {"value": 5.0, "description": "Pauza (s) po pobraniu całej galerii."},
            "GALLERY_PAUSE_THRESHOLD_MIN": {"value": 25, "description": "Min. liczba galerii do rotacji IP."},
            "GALLERY_PAUSE_THRESHOLD_MAX": {"value": 35, "description": "Max. liczba galerii do rotacji IP."},
            "ai_worker_loop_delay": {"value": 15, "description": "Opóźnienie (s) między kolejnymi cyklami pętli workera AI."}
        },
        "database": {
            "host": { "value": "localhost", "description": "Host bazy danych MySQL." },
            "user": { "value": "root", "description": "Użytkownik bazy danych." }, 
            "password": { "value": "", "description": "Hasło do bazy danych." }, 
            "database": { "value": "waifudownloader", "description": "Nazwa bazy danych." },
            "port": { "value": 3306, "description": "Port bazy danych." },
            "pool_size": { "value": 5, "description": "Rozmiar puli połączeń." }
        },
        "paths": {
            "base_data_dir_name": {"value": "Modelki", "description": "Nazwa głównego katalogu na pobrane dane."}
        },
        "ai_settings": {
            "api_base_url": {"value": "http://localhost:11434", "description": "Główny adres URL serwera Ollama."},
            "default_model_name": {"value": "llama3:latest", "description": "Domyślny model Ollama używany, gdy nie jest zdefiniowany w prompcie."}
        }
    }

def load_config(force_reload=False):
    global current_config, last_config_mtime

    defaults = get_default_config()
    if current_config is None:
        current_config = defaults
        logger.debug("current_config zainicjalizowany domyślnymi wartościami (pierwsze ładowanie lub reset).")

    reloaded_this_call = False
    config_file_path_to_use = CONFIG_FILE_PATH_CONST

    if not os.path.exists(config_file_path_to_use):
        logger.info(f"Plik {config_file_path_to_use} nie istnieje. Tworzę domyślny.")
        try:
            with open(config_file_path_to_use, 'w', encoding='utf-8') as f:
                json.dump(defaults, f, indent=4, ensure_ascii=False)
            current_config = defaults
            last_config_mtime = os.path.getmtime(config_file_path_to_use) if os.path.exists(config_file_path_to_use) else 0.0
            reloaded_this_call = True
        except Exception as e:
            logger.error(f"Błąd tworzenia {config_file_path_to_use}: {e}. Używam wbudowanych domyślnych.", exc_info=True)
            current_config = defaults
            last_config_mtime = 0.0
        return reloaded_this_call

    try:
        current_mtime = os.path.getmtime(config_file_path_to_use)
        mtime_changed = abs(current_mtime - last_config_mtime) > 0.001 if last_config_mtime != 0.0 else True

        if force_reload or mtime_changed:
            logger.info(f"Wykryto zmianę w {CONFIG_FILENAME_CONST} lub wymuszono przeładowanie. Przeładowuję... (force={force_reload}, changed={mtime_changed})")
            time.sleep(0.1)
            with open(config_file_path_to_use, 'r', encoding='utf-8') as f:
                loaded_from_file = json.load(f)

            config_to_use = get_default_config()

            for section_key, section_value in defaults.items():
                if section_key in loaded_from_file and isinstance(loaded_from_file[section_key], dict):
                    for setting_key, setting_details in section_value.items():
                        if setting_key in loaded_from_file[section_key] and \
                           isinstance(loaded_from_file[section_key][setting_key], dict) and \
                           'value' in loaded_from_file[section_key][setting_key]:
                            
                            default_val_type = type(setting_details['value'])
                            loaded_val = loaded_from_file[section_key][setting_key]['value']
                            
                            try:
                                if isinstance(loaded_val, default_val_type):
                                    config_to_use[section_key][setting_key]['value'] = loaded_val
                                elif default_val_type is float and isinstance(loaded_val, int):
                                     config_to_use[section_key][setting_key]['value'] = float(loaded_val)
                                elif default_val_type is int and isinstance(loaded_val, float) and loaded_val.is_integer():
                                     config_to_use[section_key][setting_key]['value'] = int(loaded_val)
                                else:
                                    logger.warning(f"Niewłaściwy typ wartości dla '{section_key}.{setting_key}'. Oczekiwano {default_val_type}, jest {type(loaded_val)}. Używam domyślnej: {setting_details['value']}")
                            except ValueError:
                                 logger.warning(f"Błąd konwersji typu dla '{section_key}.{setting_key}'. Wartość z pliku: '{loaded_val}'. Używam domyślnej.")
            
            current_config = config_to_use
            last_config_mtime = current_mtime
            reloaded_this_call = True
            logger.info(f"Konfiguracja załadowana/zaktualizowana z {CONFIG_FILENAME_CONST}. (mtime: {last_config_mtime:.4f})")

    except json.JSONDecodeError as e:
        logger.error(f"Błąd dekodowania JSON w {config_file_path_to_use}: {e}. Używam poprzednio załadowanej lub domyślnej konfiguracji.", exc_info=True)
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd ładowania {config_file_path_to_use}: {e}. Używam poprzednio załadowanej lub domyślnej.", exc_info=True)

    return reloaded_this_call


if current_config is None:
    logger.debug("config_handler.py importowany, wstępne ładowanie konfiguracji.")
    load_config(force_reload=True)