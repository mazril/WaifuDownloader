# -*- coding: utf-8 -*-
import os
import json
import logging
import time
import sys

# Dodaj ścieżkę do katalogu nadrzędnego, aby importować moduły aplikacji
# Zakładając, że migrate_to_sql.py jest w tym samym katalogu co pozostałe pliki .py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import constants
import utils # Dla sanitize_foldername, get_gallery_id
import config_handler # Dla konfiguracji DB
import db_manager # Dla funkcji DB

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_models_and_galleries():
    logger.info("Rozpoczynam migrację modeli i galerii...")
    models_in_list_txt = []
    if os.path.exists(constants.LIST_FILE_PATH):
        with open(constants.LIST_FILE_PATH, 'r', encoding='utf-8') as f:
            models_in_list_txt = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    else:
        logger.warning(f"Plik {constants.LIST_FILE_PATH} nie istnieje. Nie można zmigrować modeli z tego źródła.")

    migrated_models_count = 0
    migrated_galleries_count = 0

    # Modele z lista.txt (aby utworzyć wpisy w tabeli models)
    for model_name_original in models_in_list_txt:
        try:
            db_manager.get_or_create_model(model_name_original)
            migrated_models_count +=1
            logger.info(f"Przetworzono model '{model_name_original}' dla tabeli 'models'.")
        except Exception as e:
            logger.error(f"Błąd podczas przetwarzania modelu '{model_name_original}' dla tabeli 'models': {e}")


    # Dane galerii z plików <model_name>_galleries.json
    if not os.path.exists(constants.BASE_DATA_DIR):
        logger.warning(f"Katalog {constants.BASE_DATA_DIR} nie istnieje. Pomijam migrację danych galerii.")
        return

    for item_name in os.listdir(constants.BASE_DATA_DIR):
        item_path = os.path.join(constants.BASE_DATA_DIR, item_name)
        if os.path.isdir(item_path): # To jest katalog modelki
            model_name_sanitized_from_folder = item_name
            
            # Próba znalezienia oryginalnej nazwy modelki na podstawie sanitizowanej nazwy folderu
            # To może być niedokładne, jeśli sanitization było agresywne.
            # Lepszym podejściem byłoby, gdybyś miał mapowanie, lub jeśli nazwy w lista.txt są kanoniczne.
            # Dla uproszczenia, zakładamy, że modelka jest już w DB (z lista.txt) lub tworzymy nową.
            
            # Sprawdź, czy model o tej sanitizowanej nazwie istnieje
            model_entry_db = db_manager.execute_query("SELECT model_id, model_name FROM models WHERE sanitized_name = %s", (model_name_sanitized_from_folder,), fetch_one=True)
            
            current_model_id = None
            current_model_name_original = model_name_sanitized_from_folder # Domyślnie

            if model_entry_db:
                current_model_id = model_entry_db['model_id']
                current_model_name_original = model_entry_db['model_name']
                logger.info(f"Znaleziono modela '{current_model_name_original}' (ID: {current_model_id}) dla folderu '{model_name_sanitized_from_folder}'.")
            else:
                # Jeśli nie ma, spróbuj znaleźć w lista.txt na podstawie nazwy folderu (mniej dokładne)
                found_in_list = next((m for m in models_in_list_txt if utils.sanitize_foldername(m) == model_name_sanitized_from_folder), None)
                if found_in_list:
                    current_model_id = db_manager.get_or_create_model(found_in_list)
                    current_model_name_original = found_in_list
                    logger.info(f"Utworzono/Znaleziono modela '{current_model_name_original}' (ID: {current_model_id}) z lista.txt dla folderu '{model_name_sanitized_from_folder}'.")
                else:
                    # Ostateczność: utwórz model na podstawie nazwy folderu
                    current_model_id = db_manager.get_or_create_model(model_name_sanitized_from_folder) # Użyj nazwy folderu jako oryginalnej
                    current_model_name_original = model_name_sanitized_from_folder
                    logger.warning(f"Nie znaleziono dopasowania dla folderu '{model_name_sanitized_from_folder}'. Utworzono nowy model '{current_model_name_original}' (ID: {current_model_id}).")
            
            if not current_model_id:
                logger.error(f"Nie udało się uzyskać ID modelki dla folderu '{model_name_sanitized_from_folder}'. Pomijam galerie.")
                continue

            galleries_json_path = os.path.join(item_path, f"{model_name_sanitized_from_folder}{constants.MODEL_GALLERIES_SUFFIX}")
            if os.path.exists(galleries_json_path):
                logger.info(f"Przetwarzam plik galerii: {galleries_json_path}")
                try:
                    with open(galleries_json_path, 'r', encoding='utf-8') as gjf:
                        galleries_data_json = json.load(gjf)
                    
                    for gallery_id_json, gallery_info_json in galleries_data_json.items():
                        if not isinstance(gallery_info_json, dict):
                            logger.warning(f"Pominięto nieprawidłowy wpis galerii (nie jest słownikiem) dla ID '{gallery_id_json}' w pliku '{galleries_json_path}'.")
                            continue
                        try:
                            gallery_to_insert = {
                                "gallery_id": gallery_id_json,
                                "model_id": current_model_id,
                                "url": gallery_info_json.get("url"),
                                "original_title": gallery_info_json.get("original_title_from_list"), # Stara nazwa pola
                                "determined_title": gallery_info_json.get("determined_title"),
                                "folder_path": gallery_info_json.get("folder_path_on_disk"), # Stara nazwa pola
                                "expected_count": gallery_info_json.get("expected_count"),
                                "downloaded_count": gallery_info_json.get("downloaded_count", 0),
                                "status": gallery_info_json.get("status", "pending_check"),
                                "last_processed_timestamp": gallery_info_json.get("last_processed_timestamp"),
                                "error_message": gallery_info_json.get("error_message")
                            }
                            # Konwersja timestamp jeśli jest stringiem
                            if gallery_to_insert["last_processed_timestamp"] and isinstance(gallery_to_insert["last_processed_timestamp"], str):
                                try:
                                    # Sprawdź, czy format to YYYY-MM-DD HH:MM:SS
                                    time.strptime(gallery_to_insert["last_processed_timestamp"], "%Y-%m-%d %H:%M:%S")
                                except ValueError:
                                    logger.warning(f"Nieprawidłowy format daty dla galerii {gallery_id_json}: {gallery_to_insert['last_processed_timestamp']}. Ustawiam na NULL.")
                                    gallery_to_insert["last_processed_timestamp"] = None
                            
                            if not gallery_to_insert["url"]:
                                logger.warning(f"Galeria {gallery_id_json} nie ma URL. Pomijam.")
                                continue

                            db_manager.update_gallery(gallery_to_insert)
                            migrated_galleries_count += 1
                        except Exception as e_gallery:
                            logger.error(f"Błąd migracji galerii ID '{gallery_id_json}' z pliku '{galleries_json_path}': {e_gallery}")
                except json.JSONDecodeError:
                    logger.error(f"Plik JSON '{galleries_json_path}' jest uszkodzony. Pomijam.")
                except Exception as e_file:
                    logger.error(f"Błąd odczytu pliku '{galleries_json_path}': {e_file}")
            else:
                logger.debug(f"Plik galerii {galleries_json_path} nie istnieje dla folderu {model_name_sanitized_from_folder}.")

    logger.info(f"Zakończono migrację modeli ({migrated_models_count}) i galerii ({migrated_galleries_count}).")


def migrate_script_state():
    logger.info("Rozpoczynam migrację stanu skryptu (global_progress_state.json)...")
    state_file_path = os.path.join(constants.BASE_DATA_DIR, constants.GLOBAL_STATE_FILENAME) # Poprawiona ścieżka
    
    default_state = {"last_model_index_processed": -1, "current_operation": {"name": None, "params": {}}}
    script_state_data = default_state

    if os.path.exists(state_file_path):
        try:
            with open(state_file_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            
            script_state_data["last_model_index_processed"] = loaded_data.get("last_model_index_processed", -1)
            
            current_op_json = loaded_data.get("current_operation", {})
            if isinstance(current_op_json, dict):
                 script_state_data["current_operation"]["name"] = current_op_json.get("name")
                 script_state_data["current_operation"]["params"] = current_op_json.get("params", {})
            else: # Jeśli stary format current_operation był tylko stringiem
                 script_state_data["current_operation"]["name"] = current_op_json
                 script_state_data["current_operation"]["params"] = {}

            logger.info(f"Pomyślnie załadowano dane z {state_file_path}.")
        except Exception as e:
            logger.error(f"Błąd odczytu lub przetwarzania {state_file_path}: {e}. Używam domyślnego stanu.")
    else:
        logger.info(f"Plik {state_file_path} nie istnieje. Używam domyślnego stanu.")

    try:
        db_manager.set_app_state('script_state', script_state_data)
        logger.info("Pomyślnie zmigrowano stan skryptu do bazy danych.")
    except Exception as e:
        logger.error(f"Błąd zapisu stanu skryptu do bazy danych: {e}")


def migrate_priority_queue():
    logger.info("Rozpoczynam migrację kolejki priorytetowej (priority_queue.json)...")
    queue_file_path = os.path.join(constants.BASE_DATA_DIR, constants.PRIORITY_QUEUE_FILENAME) # Poprawiona ścieżka
    
    priority_queue_data = []
    if os.path.exists(queue_file_path):
        try:
            with open(queue_file_path, 'r', encoding='utf-8') as f:
                priority_queue_data = json.load(f)
            if not isinstance(priority_queue_data, list):
                logger.warning(f"Dane w {queue_file_path} nie są listą. Resetuję do pustej kolejki.")
                priority_queue_data = []
            logger.info(f"Pomyślnie załadowano {len(priority_queue_data)} elementów z {queue_file_path}.")
        except Exception as e:
            logger.error(f"Błąd odczytu {queue_file_path}: {e}. Kolejka nie zostanie zmigrowana.")
            priority_queue_data = [] # Pusta kolejka w razie błędu
    else:
        logger.info(f"Plik {queue_file_path} nie istnieje. Brak kolejki do migracji.")

    try:
        if db_manager.save_priority_queue(priority_queue_data): # Ta funkcja czyści starą kolejkę w DB
            logger.info(f"Pomyślnie zmigrowano {len(priority_queue_data)} elementów kolejki priorytetowej do bazy danych.")
        else:
            logger.error("Nie udało się zapisać kolejki priorytetowej do DB.")
    except Exception as e:
        logger.error(f"Błąd zapisu kolejki priorytetowej do bazy danych: {e}")


def migrate_incomplete_galleries():
    logger.info("Rozpoczynam migrację niekompletnych galerii (douzupelnienia.json)...")
    incomplete_file_path = os.path.join(constants.BASE_DATA_DIR, constants.INCOMPLETE_GALLERIES_FILENAME)
    
    # Ta migracja jest trochę inna - douzupelnienia.json zawierało listę URLi.
    # W nowym systemie, niekompletne galerie są identyfikowane przez status w tabeli `galleries`.
    # Możemy spróbować zaktualizować status istniejących galerii w DB, jeśli ich URL jest w douzupelnienia.json
    # i ich obecny status to np. 'completed'.
    
    # Jednakże, główna logika `process_single_gallery` i `_update_model_profile_after_scan`
    # powinna poprawnie ustawiać statusy. Migracja `douzupelnienia.json` może nie być krytyczna,
    # jeśli `*_galleries.json` zawierały już poprawne statusy.
    # Dla pewności, można dodać elementy z `douzupelnienia.json` do `priority_queue` jako galerie do przetworzenia.

    if os.path.exists(incomplete_file_path):
        try:
            with open(incomplete_file_path, 'r', encoding='utf-8') as f:
                incomplete_galleries_list = json.load(f)
            
            if not isinstance(incomplete_galleries_list, list):
                logger.warning(f"Dane w {incomplete_file_path} nie są listą. Pomijam migrację 'douzupelnienia'.")
                return

            logger.info(f"Znaleziono {len(incomplete_galleries_list)} wpisów w {incomplete_file_path}.")
            added_to_queue_count = 0
            for entry in incomplete_galleries_list:
                if isinstance(entry, dict) and 'url' in entry and 'model_name' in entry:
                    gallery_id_from_url = utils.get_gallery_id(entry['url'])
                    if gallery_id_from_url and not gallery_id_from_url.startswith("error_"):
                        item_data = {
                            'id': gallery_id_from_url,
                            'model_name': entry['model_name'],
                            'title': entry.get('gallery_title', gallery_id_from_url),
                            'count': entry.get('expected') # Może być None
                        }
                        # Dodajemy z prepend=False, aby nie mieszać z istniejącą kolejką priorytetową
                        # jeśli była już migrowana. Kolejność nie jest tu aż tak krytyczna.
                        if db_manager.add_to_priority_queue_db('gallery', item_data, prepend=False):
                            added_to_queue_count += 1
                            logger.info(f"Dodano galerię {gallery_id_from_url} (model: {entry['model_name']}) z 'douzupelnienia' do kolejki priorytetowej w DB.")
                        else:
                            logger.warning(f"Nie udało się dodać galerii {gallery_id_from_url} z 'douzupelnienia' do kolejki (możliwy duplikat).")
                    else:
                        logger.warning(f"Nie udało się uzyskać ID galerii z URL: {entry['url']} w 'douzupelnienia'.")
                else:
                    logger.warning(f"Nieprawidłowy format wpisu w {incomplete_file_path}: {entry}")
            logger.info(f"Dodano {added_to_queue_count} galerii z 'douzupelnienia.json' do kolejki priorytetowej w DB.")

        except Exception as e:
            logger.error(f"Błąd odczytu lub przetwarzania {incomplete_file_path}: {e}")
    else:
        logger.info(f"Plik {incomplete_file_path} nie istnieje. Brak niekompletnych galerii (z tego pliku) do migracji.")


def main():
    logger.info("===== Rozpoczęcie migracji danych z JSON do MySQL =====")
    
    # Załaduj konfigurację, aby db_manager miał dostęp do danych DB
    try:
        config_handler.load_config(force_reload=True)
        if not config_handler.current_config.get("database", {}).get("host", {}).get("value"):
            logger.critical("Konfiguracja bazy danych w config.json jest niekompletna lub nieobecna!")
            logger.critical("Uzupełnij sekcję 'database' w pliku config.json.")
            return
    except Exception as e:
        logger.critical(f"Krytyczny błąd ładowania konfiguracji: {e}")
        return

    # Upewnij się, że pula połączeń jest zainicjalizowana
    try:
        db_manager.initialize_connection_pool()
        if not db_manager.connection_pool:
             logger.critical("Nie udało się zainicjalizować puli połączeń z bazą danych. Sprawdź konfigurację i logi.")
             return
        # Testowe połączenie
        conn_test = db_manager.get_connection()
        conn_test.close()
        logger.info("Testowe połączenie z bazą danych udane.")
    except Exception as e_pool:
        logger.critical(f"Krytyczny błąd inicjalizacji połączenia z DB: {e_pool}", exc_info=True)
        return

    # Kolejność migracji:
    # 1. Modele i Galerie (tworzy wpisy modeli i galerii)
    # 2. Stan skryptu (last_model_index, current_operation)
    # 3. Kolejka priorytetowa
    # 4. Niekompletne galerie (douzupelnienia -> dodaje do kolejki priorytetowej)

    migrate_models_and_galleries()
    migrate_script_state()
    migrate_priority_queue()
    migrate_incomplete_galleries() # Ta funkcja doda elementy do priority_queue w DB

    logger.info("===== Migracja danych zakończona =====")
    logger.info("Przejrzyj logi powyżej w poszukiwaniu ewentualnych błędów.")
    logger.info("Możesz teraz usunąć lub zarchiwizować stare pliki JSON (oprócz config.json i lista.txt).")
    logger.info("Pamiętaj, aby nie uruchamiać tego skryptu migracyjnego ponownie, chyba że celowo.")

if __name__ == "__main__":
    main()