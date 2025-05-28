# -*- coding: utf-8 -*-
import os
import json
import constants
import utils

# --- JSON Handling ---
def load_json_file_generic(filepath, default_value=None):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Plik JSON '{filepath}' jest uszkodzony. Zwracam domyślną wartość.")
            # --- DODANO: Próba przywrócenia z backupu lub usunięcia uszkodzonego ---
            backup_path = filepath + ".bak"
            if os.path.exists(backup_path):
                print(f"   ℹ️ Próbuję przywrócić z {backup_path}...")
                try:
                    os.replace(backup_path, filepath)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e_restore:
                    print(f"   ❌ Nie udało się przywrócić backupu: {e_restore}")
            else:
                print(f"   ℹ️ Brak backupu. Rozważ usunięcie {filepath} i restart.")
            # --- KONIEC DODANO ---
        except Exception as e:
            print(f"⚠️ Błąd odczytu pliku JSON '{filepath}': {e}. Zwracam domyślną wartość.")
    return default_value if default_value is not None else {}

def save_json_file_generic(filepath, data, indent=4):
    """Zapisuje dane do pliku JSON w sposób atomowy (przez plik tymczasowy)."""
    temp_filepath = filepath + ".tmp"
    backup_filepath = filepath + ".bak"
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        # Zapisz do pliku tymczasowego
        with open(temp_filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

        # Stwórz backup istniejącego pliku (jeśli istnieje)
        if os.path.exists(filepath):
            os.replace(filepath, backup_filepath)

        # Podmień (lub stwórz) plik docelowy
        os.replace(temp_filepath, filepath)

        # Usuń stary backup, jeśli wszystko się udało
        if os.path.exists(backup_filepath):
             try: os.remove(backup_filepath)
             except Exception: pass # Niekrytyczne

        return True
    except Exception as e:
        print(f" ❌ BŁĄD zapisu do pliku JSON '{filepath}': {e}")
        # Spróbuj usunąć plik tymczasowy, jeśli istnieje
        if os.path.exists(temp_filepath):
            try: os.remove(temp_filepath)
            except Exception: pass
        # Spróbuj przywrócić backup, jeśli istnieje
        if os.path.exists(backup_filepath) and not os.path.exists(filepath):
            try:
                os.replace(backup_filepath, filepath)
                print(f"   ℹ️ Przywrócono backup {backup_filepath}")
            except Exception:
                print(f"   ❌ Nie udało się przywrócić backupu {backup_filepath}")

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
        # Opcjonalnie można zmniejszyć ilość logów, aby nie spamować konsoli
        # print(f"   💾 Zapisano dane galerii dla {model_name_sanitized} do {filepath}")
        pass

# --- Incomplete Galleries ---
def load_incomplete_galleries():
    return load_json_file_generic(constants.INCOMPLETE_GALLERIES_FILE_PATH, default_value=[])

def save_incomplete_galleries(data):
    save_json_file_generic(constants.INCOMPLETE_GALLERIES_FILE_PATH, data)

# --- Script State ---
def load_script_state():
    os.makedirs(constants.BASE_DATA_DIR, exist_ok=True)
    default_state = {"last_model_index_processed": -1, "current_operation": {"name": None, "params": {}}}
    loaded = load_json_file_generic(constants.GLOBAL_STATE_FILE_PATH, default_value=default_state)
    loaded.setdefault("last_model_index_processed", -1)
    loaded.setdefault("current_operation", {"name": None, "params": {}})
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
    print(f"   ⚙️ Ustawiono aktywną operację: {operation_name} z {state['current_operation']['params']}")

def clear_active_operation():
    state = load_script_state()
    state["current_operation"]["name"] = None
    state["current_operation"]["params"] = {}
    save_script_state(state)
    print("   ℹ️ Wyczyszczono stan aktywnej operacji.")

def update_last_model_index(index):
    state = load_script_state()
    state["last_model_index_processed"] = index
    save_script_state(state)
    # print(f"   📊 Zapisano indeks ostatniego modelu: {index}") # Można włączyć dla debugowania

# --- Model List ---
def read_model_list(path=constants.LIST_FILE_PATH): # ... (bez zmian) ...
    if not os.path.exists(path):
        print(f"🚫 Plik listy modelek '{path}' nie istnieje! Tworzę pusty.")
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# Dodaj nazwy modelek, każda w nowej linii\n")
        return []

    with open(path, 'r', encoding='utf-8') as f:
        original_lines = f.readlines()

    unique_models_ordered = []
    seen_models_for_dedup = set()
    final_lines_to_write = []
    needs_rewrite = False

    for line_content_orig in original_lines:
        original_line_ending = "\r\n" if line_content_orig.endswith("\r\n") else ("\n" if line_content_orig.endswith("\n") else "")
        line_for_processing = line_content_orig.strip()

        if not line_for_processing or line_for_processing.startswith('#'):
            final_lines_to_write.append(line_content_orig)
            if line_for_processing != line_content_orig.rstrip('\n\r'): needs_rewrite = True
            continue

        cleaned_model_name = line_for_processing.rstrip(',').rstrip()
        if cleaned_model_name != line_content_orig.strip(): needs_rewrite = True

        if cleaned_model_name and cleaned_model_name.lower() not in seen_models_for_dedup:
            seen_models_for_dedup.add(cleaned_model_name.lower())
            unique_models_ordered.append(cleaned_model_name)
            final_lines_to_write.append(cleaned_model_name + (original_line_ending or '\n'))
        elif cleaned_model_name.lower() in seen_models_for_dedup:
            print(f"  ℹ️ Znaleziono i pominięto duplikat modelki w lista.txt: '{cleaned_model_name}'")
            needs_rewrite = True
        elif not cleaned_model_name: needs_rewrite = True

    if needs_rewrite:
        print(f"  📝 Aktualizuję plik {path}...")
        try:
            with open(path, 'w', encoding='utf-8') as f: f.writelines(final_lines_to_write)
            print(f"  ✅ Plik {path} zaktualizowany.")
        except Exception as e: print(f"  ❌ Błąd podczas aktualizacji pliku {path}: {e}")

    return unique_models_ordered

# --- Priority Queue ---
def load_priority_queue(): # ... (bez zmian) ...
    return load_json_file_generic(constants.PRIORITY_QUEUE_FILE_PATH, default_value=[])

def save_priority_queue(queue_data): # ... (bez zmian) ...
    save_json_file_generic(constants.PRIORITY_QUEUE_FILE_PATH, queue_data)

def add_to_priority_queue(item_type, item_id): # ... (bez zmian) ...
    queue = load_priority_queue()
    id_to_check = utils.sanitize_foldername(item_id) if item_type == "model" else item_id
    new_item = {"type": item_type, "id": id_to_check}

    is_present = any(item.get("type") == new_item["type"] and item.get("id") == new_item["id"] for item in queue)

    if not is_present:
        queue.append(new_item)
        save_priority_queue(queue)
        print(f"  ⬆️ Dodano do kolejki priorytetowej: {item_type} - {id_to_check}")
        return True

    print(f"  ℹ️ Element {item_type} - {id_to_check} już jest w kolejce.")
    return False