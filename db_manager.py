# -*- coding: utf-8 -*-
import mysql.connector
from mysql.connector import pooling
import logging
import json
import constants
import config_handler # Potrzebne do załadowania konfiguracji DB

logger = logging.getLogger(__name__)

db_config = None
connection_pool = None

def _get_db_config():
    """Pobiera konfigurację bazy danych z config_handler."""
    global db_config
    if config_handler.current_config is None:
        config_handler.load_config(force_reload=True)

    cfg = config_handler.current_config
    # Dodajemy domyślną sekcję DB, jeśli jej nie ma (na potrzeby Python)
    cfg.setdefault("database", {
        "host": {"value": "localhost"},
        "user": {"value": "root"},
        "password": {"value": ""},
        "database": {"value": "waifudownloader"},
        "port": {"value": 3306},
        "pool_size": {"value": 5}
    })

    db_config = {
        'host': cfg['database']['host']['value'],
        'user': cfg['database']['user']['value'],
        'password': cfg['database']['password']['value'],
        'database': cfg['database']['database']['value'],
        'port': cfg['database']['port']['value'],
        'auth_plugin': 'mysql_native_password' # Często potrzebne dla MySQL 8+
    }
    return db_config, cfg['database']['pool_size']['value']

def initialize_connection_pool():
    """Inicjalizuje pulę połączeń MySQL."""
    global connection_pool
    if connection_pool:
        logger.debug("Pula połączeń już istnieje.")
        return

    config, pool_size = _get_db_config()
    if not all(config.values()):
        logger.critical("Brak pełnej konfiguracji bazy danych w config.json! Nie można utworzyć puli.")
        return

    logger.info(f"Inicjalizuję pulę połączeń MySQL (rozmiar: {pool_size})...")
    try:
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="waifu_pool",
            pool_size=pool_size,
            **config
        )
        logger.info("Pula połączeń MySQL zainicjalizowana pomyślnie.")
        # Testowe pobranie połączenia
        conn = connection_pool.get_connection()
        logger.info(f"Pomyślnie pobrano testowe połączenie z puli (ID: {conn.connection_id}).")
        conn.close()
    except mysql.connector.Error as err:
        logger.critical(f"BŁĄD KRYTYCZNY podczas inicjalizacji puli połączeń MySQL: {err}", exc_info=True)
        connection_pool = None # Upewnij się, że pula nie jest ustawiona w razie błędu

def get_connection():
    """Pobiera połączenie z puli."""
    if not connection_pool:
        logger.error("Pula połączeń nie jest zainicjalizowana. Próbuję ponownie...")
        initialize_connection_pool()
        if not connection_pool:
             raise mysql.connector.Error("Nie udało się uzyskać połączenia - pula nie istnieje.")

    try:
        conn = connection_pool.get_connection()
        logger.debug(f"Pobrano połączenie {conn.connection_id} z puli.")
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Błąd podczas pobierania połączenia z puli: {err}", exc_info=True)
        raise

def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False):
    """Wykonuje zapytanie do bazy danych."""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True) # dictionary=True zwraca wyniki jako słowniki
        cursor.execute(query, params)

        if commit:
            conn.commit()
            logger.debug(f"Zapytanie wykonane z COMMIT. Rows affected: {cursor.rowcount}")
            return cursor.lastrowid if cursor.lastrowid else cursor.rowcount
        elif fetch_one:
            result = cursor.fetchone()
            logger.debug(f"Zapytanie wykonane (fetch_one). Zwrócono: {'Dane' if result else 'Brak'}")
            return result
        elif fetch_all:
            result = cursor.fetchall()
            logger.debug(f"Zapytanie wykonane (fetch_all). Zwrócono: {len(result) if result else 0} wierszy.")
            return result
        else:
             logger.debug("Zapytanie wykonane (bez commit/fetch).")
             return None # W przypadku zapytań nie zwracających danych i bez commit

    except mysql.connector.Error as err:
        logger.error(f"Błąd wykonania zapytania: {err}\nZapytanie: {query}\nParams: {params}", exc_info=True)
        if conn and not commit: # Rollback tylko jeśli nie było commita
            conn.rollback()
        raise # Rzuć dalej, aby obsłużyć w kodzie wywołującym
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            logger.debug(f"Zwrócono połączenie do puli.")

# --- Funkcje specyficzne dla aplikacji ---

def get_or_create_model(model_name):
    """Pobiera ID modelki lub tworzy nowy wpis i zwraca ID."""
    from utils import sanitize_foldername # Import lokalny, aby uniknąć cyklicznych zależności

    sanitized = sanitize_foldername(model_name)
    query_select = "SELECT model_id FROM models WHERE model_name = %s"
    model = execute_query(query_select, (model_name,), fetch_one=True)

    if model:
        return model['model_id']
    else:
        logger.info(f"Tworzę nowy wpis dla modelki: {model_name} (sanitized: {sanitized})")
        query_insert = "INSERT INTO models (model_name, sanitized_name) VALUES (%s, %s)"
        try:
            return execute_query(query_insert, (model_name, sanitized), commit=True)
        except mysql.connector.IntegrityError:
            logger.warning(f"Model '{model_name}' lub '{sanitized}' już istnieje (IntegrityError), próbuję pobrać ponownie.")
            model = execute_query(query_select, (model_name,), fetch_one=True)
            return model['model_id'] if model else None


def get_gallery(gallery_id):
    """Pobiera dane galerii."""
    query = """
        SELECT g.*, m.model_name
        FROM galleries g
        JOIN models m ON g.model_id = m.model_id
        WHERE g.gallery_id = %s
    """
    return execute_query(query, (gallery_id,), fetch_one=True)

def get_model_galleries(model_id):
    """Pobiera wszystkie galerie dla danego modelu."""
    query = "SELECT * FROM galleries WHERE model_id = %s"
    return execute_query(query, (model_id,), fetch_all=True)

def update_gallery(gallery_data):
    """Aktualizuje lub wstawia dane galerii."""
    gallery_id = gallery_data['gallery_id']
    model_id = gallery_data['model_id']
    url = gallery_data['url']
    original_title = gallery_data.get('original_title')
    determined_title = gallery_data.get('determined_title')
    folder_path = gallery_data.get('folder_path')
    expected_count = gallery_data.get('expected_count')
    downloaded_count = gallery_data.get('downloaded_count', 0)
    status = gallery_data.get('status', 'pending_check')
    last_processed = gallery_data.get('last_processed_timestamp') # Może być None
    error_message = gallery_data.get('error_message')

    query = """
        INSERT INTO galleries (gallery_id, model_id, url, original_title, determined_title,
                               folder_path, expected_count, downloaded_count, status,
                               last_processed_timestamp, error_message)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            model_id = VALUES(model_id),
            url = VALUES(url),
            original_title = VALUES(original_title),
            determined_title = VALUES(determined_title),
            folder_path = VALUES(folder_path),
            expected_count = VALUES(expected_count),
            downloaded_count = VALUES(downloaded_count),
            status = VALUES(status),
            last_processed_timestamp = VALUES(last_processed_timestamp),
            error_message = VALUES(error_message),
            updated_at = NOW()
    """
    params = (gallery_id, model_id, url, original_title, determined_title, folder_path,
              expected_count, downloaded_count, status, last_processed, error_message)
    return execute_query(query, params, commit=True)

def get_app_state(key):
    """Pobiera wartość stanu aplikacji."""
    query = "SELECT value_text, value_json FROM app_state WHERE key_name = %s"
    result = execute_query(query, (key,), fetch_one=True)
    if result:
        return json.loads(result['value_json']) if result['value_json'] else result['value_text']
    return None

def set_app_state(key, value):
    """Ustawia wartość stanu aplikacji."""
    is_json = isinstance(value, (dict, list))
    value_json = json.dumps(value, ensure_ascii=False) if is_json else None
    value_text = str(value) if not is_json else None

    query = """
        INSERT INTO app_state (key_name, value_text, value_json)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            value_text = VALUES(value_text),
            value_json = VALUES(value_json),
            updated_at = NOW()
    """
    return execute_query(query, (key, value_text, value_json), commit=True)

def get_priority_queue():
    """Pobiera całą kolejkę priorytetową."""
    query = "SELECT queue_id, item_type, item_data FROM priority_queue ORDER BY priority ASC, added_timestamp ASC"
    results = execute_query(query, fetch_all=True)
    return [
        {"type": r['item_type'], "data": json.loads(r['item_data'])}
        for r in results
    ] if results else []

def save_priority_queue(queue_data):
    """Zapisuje *całą* kolejkę priorytetową (usuwa starą)."""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM priority_queue") # Usuń starą kolejkę
        if queue_data:
            query_insert = "INSERT INTO priority_queue (item_type, item_data, priority) VALUES (%s, %s, %s)"
            params = [
                (
                    item['type'],
                    json.dumps(item['data'], ensure_ascii=False),
                    index * 10 # Prosty system priorytetów oparty na kolejności
                )
                for index, item in enumerate(queue_data)
            ]
            cursor.executemany(query_insert, params)
        conn.commit()
        logger.info(f"Zapisano {len(queue_data)} elementów do kolejki priorytetowej.")
        return True
    except mysql.connector.Error as err:
        logger.error(f"Błąd zapisu kolejki priorytetowej: {err}", exc_info=True)
        if conn: conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def add_to_priority_queue_db(item_type, item_data, prepend=False):
    """Dodaje element do kolejki priorytetowej w DB."""
    # Prosta implementacja - pobierz, dodaj, zapisz. Można zoptymalizować.
    queue = get_priority_queue()
    new_item = {"type": item_type, "data": item_data}

    # Sprawdzanie duplikatów (uproszczone, można zrobić dokładniej w SQL)
    is_present = False
    for item_in_queue in queue:
        if item_in_queue == new_item: # Proste porównanie, może wymagać dostosowania
            is_present = True
            break

    if not is_present:
        if prepend:
            queue.insert(0, new_item)
        else:
            queue.append(new_item)
        return save_priority_queue(queue)
    else:
        logger.info(f"Element {item_data} już w kolejce (DB).")
        return False

def get_incomplete_galleries_db():
    """Pobiera galerie, które nie są 'completed' lub 'completed_with_tolerance'."""
    query = """
        SELECT g.*, m.model_name
        FROM galleries g
        JOIN models m ON g.model_id = m.model_id
        WHERE g.status NOT IN ('completed', 'completed_with_tolerance')
        AND g.expected_count IS NOT NULL AND g.downloaded_count < g.expected_count
        ORDER BY m.model_name, g.gallery_id
    """
    results = execute_query(query, fetch_all=True)
    # Formatujemy, aby przypominało starą strukturę, jeśli to konieczne
    return [
        {
            'url': r['url'],
            'expected': r['expected_count'],
            'downloaded': r['downloaded_count'],
            'folder': r['folder_path'],
            'model_name': r['model_name'],
            'gallery_title': r['determined_title'] or r['original_title'] or r['gallery_id']
         }
        for r in results
    ] if results else []

# Wywołaj inicjalizację puli przy imporcie modułu
initialize_connection_pool()