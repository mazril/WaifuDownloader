# testai_worker.py
import time
import logging
import logging.handlers
import sys
import os
import json
import random # Dla pauz

# Dodaj ścieżkę do katalogu nadrzędnego, aby importować moduły z głównego projektu
SCRIPT_DIR_WORKER = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR_WORKER)

# Importy z projektu
import config_handler
import db_manager
import services_ai

# --- Dedykowana konfiguracja loggingu dla testai_worker.py ---
log_ai_file_name = "log_ai.txt"
log_ai_file_path = os.path.join(SCRIPT_DIR_WORKER, log_ai_file_name)

logger_ai_worker = logging.getLogger("ai_worker")
logger_ai_worker.setLevel(logging.DEBUG) 

if logger_ai_worker.hasHandlers():
    logger_ai_worker.handlers.clear()

# Handler konsolowy
console_handler_ai = logging.StreamHandler(sys.stdout)
console_formatter_ai = logging.Formatter('%(asctime)s [%(levelname)-8s] [AI_WORKER:%(lineno)4d] %(message)s')
console_handler_ai.setFormatter(console_formatter_ai)
console_handler_ai.setLevel(logging.INFO) 
logger_ai_worker.addHandler(console_handler_ai)

# Handler plikowy
try:
    file_handler_ai = logging.handlers.RotatingFileHandler(
        log_ai_file_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8', delay=True
    )
    file_formatter_ai = logging.Formatter('%(asctime)s [%(levelname)-8s] [%(name)-20s:%(lineno)4d] %(message)s')
    file_handler_ai.setFormatter(file_formatter_ai)
    file_handler_ai.setLevel(logging.DEBUG) 
    logger_ai_worker.addHandler(file_handler_ai)
    logger_ai_worker.info(f"Logowanie AI Workera do pliku skonfigurowane: {log_ai_file_path}")
except Exception as e_log_ai:
    print(f"KRYTYCZNY BŁĄD: Nie udało się skonfigurować logowania AI Workera do pliku '{log_ai_file_path}': {e_log_ai}")
    logger_ai_worker.error(f"KRYTYCZNY BŁĄD: Nie udało się skonfigurować logowania AI Workera do pliku '{log_ai_file_path}': {e_log_ai}", exc_info=True)


try:
    # Poprawiony blok ładowania i sprawdzania konfiguracji
    config_handler.load_config(force_reload=True)
    ai_settings = config_handler.current_config.get("ai_settings", {})
    if not ai_settings.get("api_base_url", {}).get("value"):
        logger_ai_worker.critical("Krytyczna konfiguracja 'ai_settings.api_base_url' nie jest ustawiona w config.json!")
        sys.exit(1)
except Exception as e_cfg_load:
    logger_ai_worker.critical(f"Nie udało się załadować konfiguracji na starcie AI Workera: {e_cfg_load}", exc_info=True)
    sys.exit(1)


def process_pending_ai_tasks():
    logger_ai_worker.info("Rozpoczynam sprawdzanie zadań AI...")
    
    if not db_manager.connection_pool:
        logger_ai_worker.warning("Pula połączeń DB nie była zainicjalizowana przez AI Workera. Próbuję zainicjalizować...")
        db_manager.initialize_connection_pool()
        if not db_manager.connection_pool:
            logger_ai_worker.error("Nie udało się zainicjalizować puli połączeń DB. Pomijam ten cykl AI.")
            return

    if not services_ai.initialize_ai_model():
        logger_ai_worker.error("Nie udało się zainicjalizować/połączyć z serwerem AI (Ollama). Pomijam ten cykl AI.")
        return

    # 1. Zadania produkcyjne AI
    try:
        prod_tasks_query = """
            SELECT g.gallery_id, g.source_page_title, g.original_title, g.gallery_description, g.tags_json, m.model_name
            FROM galleries g
            JOIN models m ON g.model_id = m.model_id
            WHERE g.status = 'pending_production_ai' AND g.initial_data_fetched = TRUE
            ORDER BY g.updated_at ASC LIMIT 5
        """
        prod_tasks = db_manager.execute_query(prod_tasks_query, fetch_all=True)

        if prod_tasks:
            logger_ai_worker.info(f"AI Worker: Znaleziono {len(prod_tasks)} zadań produkcyjnych AI. Pierwsze: {prod_tasks[0]['gallery_id'] if prod_tasks else 'N/A'}")
            for task in prod_tasks:
                gallery_id = task['gallery_id']
                model_name_for_task = task.get('model_name', '') 
                logger_ai_worker.info(f"  Przetwarzanie (Prod AI) dla galerii: {gallery_id} (Modelka: {model_name_for_task})")
                
                text_to_process = task.get("source_page_title") or task.get("original_title") or gallery_id
                description_from_db = task.get("gallery_description")
                tags_str = task.get("tags_json")
                tags_data = json.loads(tags_str) if tags_str else {}
                
                structured_hints = {}
                if tags_data.get("cosplay") and isinstance(tags_data["cosplay"], list) and tags_data["cosplay"]:
                    structured_hints["character_hint"] = tags_data["cosplay"][0].strip()
                if tags_data.get("fandom") and isinstance(tags_data["fandom"], list) and tags_data["fandom"]:
                    structured_hints["series_hint"] = tags_data["fandom"][0].strip()

                logger_ai_worker.debug(f"    Dane dla AI (Prod) {gallery_id}: Tekst='{text_to_process[:100]}...', Opis='{description_from_db[:100] if description_from_db else 'Brak'}', Negatywne='{model_name_for_task}', Hinty={structured_hints}")

                ai_raw_title = services_ai.extract_gallery_name_ollama(
                    text_to_process,
                    negative_prompts_list=[model_name_for_task] if model_name_for_task else None,
                    structured_hints_input=structured_hints,
                    prompt_config_id="production",
                    context_description=description_from_db
                )
                logger_ai_worker.debug(f"    Surowa odpowiedź AI (Prod) dla {gallery_id}: '{ai_raw_title}'")
                final_title = services_ai.post_process_ai_title(ai_raw_title, model_name_to_avoid_in_title=model_name_for_task)
                logger_ai_worker.debug(f"    Przetworzony tytuł AI (Prod) dla {gallery_id}: '{final_title}'")

                if final_title: 
                    db_manager.update_gallery(gallery_id, determined_title=final_title, status='pending_check')
                    logger_ai_worker.info(f"    Sukces (Prod AI): {gallery_id} -> Tytuł: '{final_title}', Status: 'pending_check'")
                else:
                    db_manager.update_gallery(gallery_id, status='error_ai_prod') 
                    logger_ai_worker.error(f"    Błąd (Prod AI) dla {gallery_id}: AI zwróciło pusty lub niepoprawny tytuł po przetworzeniu. Surowa odp: '{ai_raw_title}'")
                time.sleep(random.uniform(0.5, 1.5)) 
        else:
            pass

    except Exception as e_prod:
        logger_ai_worker.error(f"Krytyczny błąd podczas przetwarzania zadań produkcyjnych AI: {e_prod}", exc_info=True)

    # 2. Zadania testowe AI
    try:
        test_tasks_query = """
            SELECT g.gallery_id, g.status, g.initial_data_fetched, g.updated_at, g.source_page_title, g.original_title, g.gallery_description, g.tags_json, m.model_name
            FROM galleries g
            JOIN models m ON g.model_id = m.model_id
            WHERE g.status = 'pending_test_ai' AND g.initial_data_fetched = TRUE
            ORDER BY g.updated_at ASC LIMIT 5
        """
        test_tasks = db_manager.execute_query(test_tasks_query, fetch_all=True)
        
        if test_tasks:
            logger_ai_worker.info(f"AI Worker: Znaleziono {len(test_tasks)} zadań testowych. Pierwsze ID: {test_tasks[0]['gallery_id'] if test_tasks else 'N/A'}.")
            
            for task in test_tasks:
                gallery_id = task['gallery_id']
                model_name_for_task = task.get('model_name', '')
                logger_ai_worker.info(f"  Przetwarzanie (Test AI) dla galerii: {gallery_id} (Modelka: {model_name_for_task})")

                text_to_process = task.get("source_page_title") or task.get("original_title") or gallery_id
                description_from_db = task.get("gallery_description")
                tags_str = task.get("tags_json")
                tags_data = json.loads(tags_str) if tags_str else {}
                
                structured_hints = {}
                if tags_data.get("cosplay") and isinstance(tags_data["cosplay"], list) and tags_data["cosplay"]:
                    structured_hints["character_hint"] = tags_data["cosplay"][0].strip()
                if tags_data.get("fandom") and isinstance(tags_data["fandom"], list) and tags_data["fandom"]:
                    structured_hints["series_hint"] = tags_data["fandom"][0].strip()

                logger_ai_worker.debug(f"    Dane dla AI (Test) {gallery_id}: Tekst='{text_to_process[:100]}...', Opis='{description_from_db[:100] if description_from_db else 'Brak'}', Negatywne='{model_name_for_task}', Hinty={structured_hints}")
                
                ai_raw_title = services_ai.extract_gallery_name_ollama(
                    text_to_process,
                    negative_prompts_list=[model_name_for_task] if model_name_for_task else None,
                    structured_hints_input=structured_hints,
                    prompt_config_id="test",
                    context_description=description_from_db
                )
                logger_ai_worker.debug(f"    Surowa odpowiedź AI (Test) dla {gallery_id}: '{ai_raw_title}'")
                final_title = services_ai.post_process_ai_title(ai_raw_title, model_name_to_avoid_in_title=model_name_for_task)
                logger_ai_worker.debug(f"    Przetworzony tytuł AI (Test) dla {gallery_id}: '{final_title}'")

                if final_title: 
                    db_manager.update_gallery(gallery_id, test_ai_title=final_title, status='test_completed')
                    logger_ai_worker.info(f"    Sukces (Test AI): {gallery_id} -> Tytuł testowy: '{final_title}', Status: 'test_completed'")
                else:
                    db_manager.update_gallery(gallery_id, status='error_ai_test')
                    logger_ai_worker.error(f"    Błąd (Test AI) dla {gallery_id}: AI zwróciło pusty lub niepoprawny tytuł po przetworzeniu. Surowa odp: '{ai_raw_title}'")
                time.sleep(random.uniform(0.5, 1.5)) 
        else:
            pass
            
    except Exception as e_test:
        logger_ai_worker.error(f"Krytyczny błąd podczas przetwarzania zadań testowych AI: {e_test}", exc_info=True)


if __name__ == "__main__":
    logger_ai_worker.info(f"Uruchomiono worker AI ({os.path.basename(__file__)}).")
    
    if not db_manager.connection_pool: 
        logger_ai_worker.info("Inicjalizuję pulę połączeń DB z poziomu AI Workera...")
        db_manager.initialize_connection_pool() 
        if not db_manager.connection_pool: 
            logger_ai_worker.critical("Nie udało się zainicjalizować puli DB w AI Workerze. Zakończenie.")
            sys.exit(1)
            
    worker_loop_delay = 15 
    try:
        if config_handler.current_config: 
            ai_worker_config = config_handler.current_config.get("pauses_and_rotation", {}).get("ai_worker_loop_delay", {"value": 15})
            worker_loop_delay = ai_worker_config.get("value", 15)
        else:
            logger_ai_worker.warning("Nie można załadować konfiguracji do odczytu ai_worker_loop_delay. Używam domyślnej wartości 15s.")
    except Exception as e_cfg_delay:
        logger_ai_worker.warning(f"Błąd odczytu ai_worker_loop_delay z konfiguracji: {e_cfg_delay}. Używam domyślnej wartości 15s.")

    logger_ai_worker.info(f"Worker AI będzie sprawdzał zadania co {worker_loop_delay} sekund.")

    try:
        while True:
            if config_handler.load_config(): 
                 logger_ai_worker.info("Konfiguracja przeładowana dynamicznie w AI Workerze.")
                 ai_worker_config_loop = config_handler.current_config.get("pauses_and_rotation", {}).get("ai_worker_loop_delay", {"value": 15})
                 new_delay = ai_worker_config_loop.get("value", 15)
                 if new_delay != worker_loop_delay:
                     logger_ai_worker.info(f"Zmieniono opóźnienie pętli AI Workera z {worker_loop_delay}s na {new_delay}s.")
                     worker_loop_delay = new_delay
            
            process_pending_ai_tasks()
            
            logger_ai_worker.info(f"Worker AI: Zakończono cykl. Czekam {worker_loop_delay}s przed następnym sprawdzeniem.")
            time.sleep(worker_loop_delay)
    except KeyboardInterrupt:
        logger_ai_worker.info("Worker AI zatrzymany przez użytkownika (Ctrl+C).")
    except Exception as e_main_worker:
        logger_ai_worker.critical(f"Krytyczny błąd w głównej pętli workera AI: {e_main_worker}", exc_info=True)
    finally:
        logger_ai_worker.info("Worker AI zakończył działanie.")