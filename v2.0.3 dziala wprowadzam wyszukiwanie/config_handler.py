# -*- coding: utf-8 -*-
import os
import json
import time
import constants
import logging

logger = logging.getLogger(__name__)

current_config = None
last_config_mtime = 0.0

def get_default_config():
    """Zwraca domyślną konfigurację (bez sekcji database)."""
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
            "incomplete_gallery_completion_tolerance": {"value": 4, "description": "Maksymalna liczba brakujących obrazów, przy której galeria jest nadal uznawana za 'ukończoną z tolerancją'."}
        },
        "pauses_and_rotation": {
            "gallery_pause": {"value": 5.0, "description": "Pauza (s) po pobraniu całej galerii."},
            "GALLERY_PAUSE_THRESHOLD_MIN": {"value": 25, "description": "Min. liczba galerii do rotacji IP."},
            "GALLERY_PAUSE_THRESHOLD_MAX": {"value": 35, "description": "Max. liczba galerii do rotacji IP."}
        },
        "database": {
            "host": { "value": "localhost", "description": "Host bazy danych MySQL." },
            "user": { "value": "root", "description": "Użytkownik bazy danych." },
            "password": { "value": "", "description": "Hasło do bazy danych." },
            "database": { "value": "waifudownloader", "description": "Nazwa bazy danych." },
            "port": { "value": 3306, "description": "Port bazy danych." },
            "pool_size": { "value": 5, "description": "Rozmiar puli połączeń." }
        }
    }

def load_config(force_reload=False):
    global current_config, last_config_mtime

    defaults = get_default_config()
    if current_config is None:
        current_config = defaults
        logger.debug("current_config zainicjalizowany domyślnymi wartościami po raz pierwszy.")

    reloaded_this_call = False
    config_file_path = constants.CONFIG_FILE_PATH

    if not os.path.exists(config_file_path):
        logger.info(f"Plik {config_file_path} nie istnieje. Tworzę domyślny.")
        try:
            with open(config_file_path, 'w', encoding='utf-8') as f:
                json.dump(defaults, f, indent=4, ensure_ascii=False)
            current_config = defaults
            last_config_mtime = os.path.getmtime(config_file_path) if os.path.exists(config_file_path) else 0.0
            reloaded_this_call = True
        except Exception as e:
            logger.error(f"Błąd tworzenia {config_file_path}: {e}. Używam wbudowanych domyślnych.", exc_info=True)
            current_config = defaults
            last_config_mtime = 0.0
        return reloaded_this_call

    try:
        current_mtime = os.path.getmtime(config_file_path)
        mtime_changed = abs(current_mtime - last_config_mtime) > 0.001

        if force_reload or mtime_changed:
            logger.info(f"Wykryto zmianę w config.json lub wymuszono przeładowanie. Przeładowuję... (force={force_reload}, changed={mtime_changed})")
            time.sleep(0.1)
            with open(config_file_path, 'r', encoding='utf-8') as f:
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
                            if isinstance(loaded_val, default_val_type):
                                config_to_use[section_key][setting_key]['value'] = loaded_val
                            else:
                                logger.warning(f"Niewłaściwy typ wartości dla '{section_key}.{setting_key}'. Oczekiwano {default_val_type}, jest {type(loaded_val)}. Używam domyślnej.")
                        else:
                             logger.debug(f"Klucz '{section_key}.{setting_key}' nie znaleziony w config.json. Używam domyślnej.")
                else:
                     logger.debug(f"Sekcja '{section_key}' nie znaleziona w config.json. Używam domyślnych.")

            current_config = config_to_use
            last_config_mtime = current_mtime
            reloaded_this_call = True
            logger.info(f"Konfiguracja załadowana/zaktualizowana. (mtime: {last_config_mtime:.4f})")
        else:
            logger.debug("Konfiguracja nie wymaga przeładowania.")

    except json.JSONDecodeError as e:
        logger.error(f"Błąd dekodowania JSON w {config_file_path}: {e}. Używam starych/domyślnych.", exc_info=True)
        last_config_mtime = 0.0
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd ładowania {config_file_path}: {e}. Używam starych/domyślnych.", exc_info=True)
        last_config_mtime = 0.0

    # Jeśli konfiguracja została przeładowana, poinformuj db_manager, aby ewentualnie odświeżył pulę
    if reloaded_this_call:
        try:
            import db_manager
            db_manager.initialize_connection_pool() # Spróbuj odświeżyć pulę
        except ImportError:
            logger.warning("Nie można zaimportować db_manager do odświeżenia puli.")
        except Exception as e_pool:
            logger.error(f"Błąd podczas próby odświeżenia puli DB po przeładowaniu config: {e_pool}")


    return reloaded_this_call


# Początkowe ładowanie konfiguracji
if current_config is None:
    logger.debug("Początkowe wywołanie load_config() z poziomu modułu (force_reload=True).")
    load_config(force_reload=True)