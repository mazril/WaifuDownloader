# -*- coding: utf-8 -*-
import os
import json
import constants
import utils
import logging
import db_manager # Nowy import

logger = logging.getLogger(__name__)

# --- JSON Handling (Usunięto load/save_json_file_generic) ---
# Pozostawiamy tylko funkcje niezwiązane z bazą danych, jeśli są potrzebne.
# W tym przypadku, większość przeniesiona do DB lub usunięta.

# --- Model Data ---
def get_model_data_dir(model_name_sanitized):
    """Zwraca ścieżkę do katalogu modelki (pozostaje dla plików fizycznych)."""
    return os.path.join(constants.BASE_DATA_DIR, model_name_sanitized)

def load_model_galleries_data(model_name_original):
    """Wczytuje dane galerii modelki z bazy danych."""
    model_id = db_manager.get_or_create_model(model_name_original)
    if not model_id:
        return {}
    galleries = db_manager.get_model_galleries(model_id)
    # Konwertuj listę na słownik {gallery_id: gallery_data} dla zgodności
    return {g['gallery_id']: g for g in galleries} if galleries else {}

def save_gallery_data(gallery_data):
    """Zapisuje dane pojedynczej galerii do bazy danych."""
    return db_manager.update_gallery(gallery_data)

# --- Incomplete Galleries (Teraz pobierane z DB) ---
def load_incomplete_galleries():
    """Wczytuje niekompletne galerie z bazy danych."""
    return db_manager.get_incomplete_galleries_db()

# --- Script State (Teraz w DB) ---
def load_script_state():
    """Wczytuje stan skryptu z bazy danych."""
    state = db_manager.get_app_state('script_state')
    default_state = {"last_model_index_processed": -1, "current_operation": {"name": None, "params": {}}}
    if not state:
        db_manager.set_app_state('script_state', default_state)
        return default_state

    # Upewnij się, że wszystkie kluczowe pola istnieją
    state.setdefault("last_model_index_processed", -1)
    state.setdefault("current_operation", {"name": None, "params": {}})
    if not isinstance(state["current_operation"], dict):
        state["current_operation"] = {"name": None, "params": {}}
    state["current_operation"].setdefault("name", None)
    state["current_operation"].setdefault("params", {})
    return state

def save_script_state(state_data):
    """Zapisuje stan skryptu do bazy danych."""
    db_manager.set_app_state('script_state', state_data)

def update_active_operation(operation_name, params=None):
    state = load_script_state()
    state["current_operation"]["name"] = operation_name
    state["current_operation"]["params"] = params if params is not None else {}
    save_script_state(state)
    logger.info(f"Ustawiono aktywną operację (DB): {operation_name} z parametrami: {state['current_operation']['params']}")

def clear_active_operation():
    state = load_script_state()
    state["current_operation"]["name"] = None
    state["current_operation"]["params"] = {}
    save_script_state(state)
    logger.info("Wyczyszczono stan aktywnej operacji (DB).")

def update_last_model_index(index):
    state = load_script_state()
    state["last_model_index_processed"] = index
    save_script_state(state)
    logger.debug(f"Zaktualizowano indeks ostatnio przetworzonego modelu na: {index} (DB)")

# --- Model List (Pozostaje odczyt z pliku txt) ---
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

# --- Priority Queue (Teraz w DB) ---
def load_priority_queue():
    """Wczytuje kolejkę priorytetową z bazy danych."""
    return db_manager.get_priority_queue()

def save_priority_queue(queue_data):
    """Zapisuje kolejkę priorytetową do bazy danych."""
    return db_manager.save_priority_queue(queue_data)

def add_to_priority_queue(item_type, item_data, prepend=False):
    """Dodaje element do kolejki priorytetowej w DB."""
    return db_manager.add_to_priority_queue_db(item_type, item_data, prepend)