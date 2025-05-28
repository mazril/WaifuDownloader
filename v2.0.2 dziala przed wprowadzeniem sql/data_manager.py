# -*- coding: utf-8 -*-
import os
import json
import constants
import utils # Zakładam, że utils.py istnieje i zawiera np. sanitize_foldername
import logging

logger = logging.getLogger(__name__)

# --- JSON Handling ---
def load_json_file_generic(filepath, default_value=None):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Plik JSON '{filepath}' jest uszkodzony. Próbuję przywrócić z backupu lub zwracam domyślną wartość.")
            backup_path = filepath + ".bak"
            if os.path.exists(backup_path):
                logger.info(f"Próbuję przywrócić z {backup_path}...")
                try:
                    import shutil
                    temp_restore_path = filepath + ".restore_tmp"
                    shutil.copy2(backup_path, temp_restore_path)
                    os.replace(temp_restore_path, filepath) # Atomowe zastąpienie
                    logger.info(f"Przywrócono {filepath} z {backup_path}. Próbuję wczytać ponownie.")
                    with open(filepath, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e_restore:
                    logger.error(f"Nie udało się przywrócić backupu dla '{filepath}': {e_restore}", exc_info=True)
            else:
                logger.info(f"Brak pliku backup '{backup_path}' dla '{filepath}'.")
        except Exception as e:
            logger.error(f"Błąd odczytu pliku JSON '{filepath}': {e}. Zwracam domyślną wartość.", exc_info=True)
    else:
        logger.debug(f"Plik '{filepath}' nie istnieje. Zwracam domyślną wartość.")
    return default_value if default_value is not None else {}

def save_json_file_generic(filepath, data, indent=4):
    temp_filepath = filepath + ".tmp"
    backup_filepath = filepath + ".bak"
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(temp_filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

        if os.path.exists(filepath):
            try:
                if os.path.abspath(filepath) != os.path.abspath(backup_filepath): # Upewnij się, że nie nadpisujesz samego siebie
                    os.replace(filepath, backup_filepath) 
                    logger.debug(f"Utworzono backup: {backup_filepath} z {filepath}")
                else:
                    logger.warning(f"Ścieżka pliku i backupu jest taka sama, pomijam tworzenie backupu: {filepath}")
            except Exception as e_backup:
                logger.warning(f"Nie udało się utworzyć backupu {backup_filepath} dla {filepath}: {e_backup}")
        
        os.replace(temp_filepath, filepath) # Atomowe zastąpienie
        return True
    except Exception as e:
        logger.error(f"BŁĄD zapisu do pliku JSON '{filepath}': {e}", exc_info=True)
        if os.path.exists(temp_filepath):
            try: os.remove(temp_filepath)
            except Exception: pass # Ignoruj błędy usuwania tymczasowego pliku
        
        # Spróbuj przywrócić backup, jeśli główny plik został uszkodzony/usunięty podczas operacji
        if os.path.exists(backup_filepath) and not os.path.exists(filepath):
            try:
                os.replace(backup_filepath, filepath) # Przywróć backup
                logger.info(f"Przywrócono backup {backup_filepath} do {filepath} po błędzie zapisu.")
            except Exception as e_restore_fail:
                logger.error(f"Nie udało się przywrócić backupu {backup_filepath} po błędzie zapisu: {e_restore_fail}")
        return False

# --- Model Data ---
def get_model_data_dir(model_name_sanitized):
    return os.path.join(constants.BASE_DATA_DIR, model_name_sanitized)

def get_model_galleries_filepath(model_name_sanitized):
    model_dir = get_model_data_dir(model_name_sanitized)
    return os.path.join(model_dir, f"{model_name_sanitized}{constants.MODEL_GALLERIES_SUFFIX}")

def load_model_galleries_data(model_name_sanitized):
    filepath = get_model_galleries_filepath(model_name_sanitized)
    return load_json_file_generic(filepath, default_value={})

def save_model_galleries_data(model_name_sanitized, data):
    filepath = get_model_galleries_filepath(model_name_sanitized)
    if save_json_file_generic(filepath, data):
        logger.debug(f"Zapisano dane galerii dla {model_name_sanitized} do {filepath}")

# --- Incomplete Galleries ---
def load_incomplete_galleries():
    return load_json_file_generic(constants.INCOMPLETE_GALLERIES_FILE_PATH, default_value=[])

def save_incomplete_galleries(data):
    save_json_file_generic(constants.INCOMPLETE_GALLERIES_FILE_PATH, data)

# --- Script State ---
def load_script_state():
    os.makedirs(constants.BASE_DATA_DIR, exist_ok=True) # Upewnij się, że katalog istnieje
    default_state = {"last_model_index_processed": -1, "current_operation": {"name": None, "params": {}}}
    loaded = load_json_file_generic(constants.GLOBAL_STATE_FILE_PATH, default_value=default_state)
    
    # Upewnij się, że wszystkie kluczowe pola istnieją
    loaded.setdefault("last_model_index_processed", -1)
    loaded.setdefault("current_operation", {"name": None, "params": {}})
    if not isinstance(loaded["current_operation"], dict): # Napraw, jeśli current_operation nie jest słownikiem
        loaded["current_operation"] = {"name": None, "params": {}}
    loaded["current_operation"].setdefault("name", None)
    loaded["current_operation"].setdefault("params", {})
    return loaded

def save_script_state(state_data):
    save_json_file_generic(constants.GLOBAL_STATE_FILE_PATH, state_data)

def update_active_operation(operation_name, params=None):
    state = load_script_state()
    state["current_operation"]["name"] = operation_name
    state["current_operation"]["params"] = params if params is not None else {}
    save_script_state(state)
    logger.info(f"Ustawiono aktywną operację: {operation_name} z parametrami: {state['current_operation']['params']}")

def clear_active_operation():
    state = load_script_state()
    state["current_operation"]["name"] = None
    state["current_operation"]["params"] = {}
    save_script_state(state)
    logger.info("Wyczyszczono stan aktywnej operacji.")

def update_last_model_index(index):
    state = load_script_state()
    state["last_model_index_processed"] = index
    save_script_state(state)
    logger.debug(f"Zaktualizowano indeks ostatnio przetworzonego modelu na: {index}")

# --- Model List ---
def read_model_list(path=constants.LIST_FILE_PATH):
    if not os.path.exists(path):
        logger.warning(f"Plik listy modelek '{path}' nie istnieje! Tworzę pusty.")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write("# Dodaj nazwy modelek, każda w nowej linii\n")
        except Exception as e:
            logger.error(f"Nie udało się utworzyć pliku lista.txt: {e}")
        return []

    try:
        with open(path, 'r', encoding='utf-8') as f:
            original_lines = f.readlines()
    except Exception as e:
        logger.error(f"Nie udało się odczytać pliku lista.txt: {e}")
        return []

    unique_models_ordered = []
    seen_models_for_dedup = set()
    final_lines_to_write = []
    needs_rewrite = False

    for line_content_orig in original_lines:
        original_line_ending = ""
        if line_content_orig.endswith("\r\n"): original_line_ending = "\r\n"
        elif line_content_orig.endswith("\n"): original_line_ending = "\n"
        
        line_for_processing = line_content_orig.strip()

        if not line_for_processing or line_for_processing.startswith('#'):
            final_lines_to_write.append(line_content_orig)
            if line_for_processing != line_content_orig.rstrip('\n\r'): needs_rewrite = True
            continue
        
        cleaned_model_name = line_for_processing.rstrip(',').strip()
        if cleaned_model_name != line_for_processing: needs_rewrite = True
        
        if cleaned_model_name != line_content_orig.strip(): needs_rewrite = True

        if cleaned_model_name and cleaned_model_name.lower() not in seen_models_for_dedup:
            seen_models_for_dedup.add(cleaned_model_name.lower())
            unique_models_ordered.append(cleaned_model_name)
            final_lines_to_write.append(cleaned_model_name + (original_line_ending or '\n'))
        elif cleaned_model_name.lower() in seen_models_for_dedup:
            logger.info(f"Znaleziono i pominięto duplikat modelki w lista.txt: '{cleaned_model_name}'")
            needs_rewrite = True
        elif not cleaned_model_name and line_content_orig.strip(): needs_rewrite = True

    if needs_rewrite:
        logger.info(f"Aktualizuję plik {path} (usuwanie duplikatów/czyszczenie)...")
        try:
            with open(path, 'w', encoding='utf-8') as f: f.writelines(final_lines_to_write)
            logger.info(f"Plik {path} zaktualizowany.")
        except Exception as e: 
            logger.error(f"Błąd podczas aktualizacji pliku {path}: {e}", exc_info=True)
            
    return unique_models_ordered

# --- Priority Queue ---
def load_priority_queue():
    return load_json_file_generic(constants.PRIORITY_QUEUE_FILE_PATH, default_value=[])

def save_priority_queue(queue_data):
    save_json_file_generic(constants.PRIORITY_QUEUE_FILE_PATH, queue_data)

def add_to_priority_queue(item_type, item_data, prepend=False):
    """
    Dodaje element do kolejki priorytetowej.
    item_data (słownik dla galerii, string dla scan_model) jest teraz przechowywane pod kluczem "data".
    """
    queue = load_priority_queue()
    
    new_item = {
        "type": item_type,
        "data": item_data  # Przechowaj cały ładunek pod kluczem "data"
    }

    is_present = False
    for item_in_queue in queue:
        if item_in_queue.get("type") == new_item.get("type"):
            queued_payload = item_in_queue.get("data")
            new_payload = new_item.get("data")
            
            if new_item["type"] == "gallery":
                # queued_payload i new_payload powinny być słownikami
                if isinstance(queued_payload, dict) and isinstance(new_payload, dict):
                    # Porównujemy ID galerii wewnątrz payloadu
                    if queued_payload.get("id") == new_payload.get("id"): 
                        is_present = True; break
            elif new_item["type"] == "scan_model":
                # queued_payload i new_payload powinny być stringami (nazwami modeli)
                if queued_payload == new_payload:
                    is_present = True; break
            # Można dodać obsługę innych typów jeśli będą potrzebne

    if not is_present:
        if prepend:
            queue.insert(0, new_item)
            logger.info(f"Dodano na POCZĄTEK kolejki priorytetowej: {new_item}")
        else:
            queue.append(new_item)
            logger.info(f"Dodano na KONIEC kolejki priorytetowej: {new_item}")
        save_priority_queue(queue)
        return True
        
    logger.info(f"Element {new_item.get('data')} (typ: {item_type}) już jest w kolejce lub podobny istnieje. Nie dodano.")
    return False