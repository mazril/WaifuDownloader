# -*- coding: utf-8 -*-
import os
import json
import constants # constants.py będzie teraz cieńszy
import utils
import logging
import db_manager 

logger = logging.getLogger(__name__)

# --- Model Data ---
def get_model_data_dir(model_name_sanitized):
    """Zwraca ścieżkę do katalogu modelki (pozostaje dla plików fizycznych)."""
    return os.path.join(constants.BASE_DATA_DIR, model_name_sanitized)

def load_model_galleries_data(model_name_original):
    """Wczytuje dane galerii modelki z bazy danych."""
    model_id = db_manager.get_or_create_model(model_name_original)
    if not model_id:
        logger.warning(f"Nie znaleziono ID dla modelki: {model_name_original} podczas ładowania galerii.")
        return {}
    galleries = db_manager.get_model_galleries(model_id)
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
        # Jeśli stan nie istnieje w DB, utwórz go z wartościami domyślnymi
        logger.info("Brak 'script_state' w DB, tworzę domyślny.")
        db_manager.set_app_state('script_state', default_state)
        return default_state

    state.setdefault("last_model_index_processed", -1)
    current_op = state.get("current_operation")
    if not isinstance(current_op, dict):
        state["current_operation"] = {"name": None, "params": {}}
    else:
        current_op.setdefault("name", None)
        current_op.setdefault("params", {})
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

def update_last_model_index(index): # Indeks będzie teraz mniej istotny, bo iterujemy po ID z DB
    state = load_script_state()
    # Zamiast indeksu, można by przechowywać ID ostatnio przetwarzanej modelki,
    # ale dla zachowania spójności z obecną logiką menu, zostawiamy indeks.
    # Jednak pętla w processing.py powinna iterować po modelach z DB.
    state["last_model_index_processed"] = index 
    save_script_state(state)
    logger.debug(f"Zaktualizowano indeks ostatnio przetworzonego modelu na: {index} (DB)")

# --- Model List (Teraz z bazy danych) ---
def read_model_list():
    """Odczytuje listę nazw modelek z tabeli 'models' w bazie danych."""
    logger.debug("Odczytywanie listy modelek z bazy danych...")
    try:
        models_db = db_manager.execute_query("SELECT model_name FROM models ORDER BY model_name ASC", fetch_all=True)
        if models_db:
            model_names = [row['model_name'] for row in models_db]
            logger.info(f"Pobrano {len(model_names)} modelek z bazy danych.")
            return model_names
        else:
            logger.info("Brak modelek w bazie danych.")
            return []
    except Exception as e:
        logger.error(f"Błąd podczas odczytu listy modelek z bazy danych: {e}", exc_info=True)
        return []

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