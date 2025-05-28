# -*- coding: utf-8 -*-
import mysql.connector
from mysql.connector import pooling
import logging
import json
import constants # Może być nadal potrzebny dla niektórych ścieżek, jeśli nie są w config
import config_handler 

logger = logging.getLogger(__name__)

db_config_details = None # Zmieniono nazwę z db_config, aby uniknąć konfliktu z modułem
connection_pool = None

def _get_db_config():
    """Pobiera konfigurację bazy danych z config_handler."""
    global db_config_details 
    if config_handler.current_config is None:
        config_handler.load_config(force_reload=True)

    cfg = config_handler.current_config
    cfg.setdefault("database", {
        "host": {"value": "localhost"}, "user": {"value": "root"},
        "password": {"value": ""}, "database": {"value": "waifudownloader"},
        "port": {"value": 3306}, "pool_size": {"value": 5}
    })

    db_config_details = {
        'host': cfg['database']['host']['value'],
        'user': cfg['database']['user']['value'],
        'password': cfg['database']['password']['value'],
        'database': cfg['database']['database']['value'],
        'port': cfg['database']['port']['value'],
        'auth_plugin': 'mysql_native_password' 
    }
    return db_config_details, cfg['database']['pool_size']['value']

def initialize_connection_pool():
    """Inicjalizuje pulę połączeń MySQL."""
    global connection_pool
    if connection_pool:
        try: # Sprawdź, czy pula nadal działa
            conn_test = connection_pool.get_connection()
            conn_test.close()
            logger.debug("Pula połączeń już istnieje i działa.")
            return
        except mysql.connector.Error as pool_error:
            logger.warning(f"Pula połączeń istnieje, ale wystąpił błąd przy pobieraniu połączenia: {pool_error}. Inicjalizuję ponownie.")
            connection_pool = None # Wymuś ponowną inicjalizację

    config_data, pool_size = _get_db_config()
    if not all(config_data.values()): # Sprawdza czy wszystkie wartości (host, user, db) są ustawione
        logger.critical("Brak pełnej konfiguracji bazy danych (host, user, database) w config.json! Nie można utworzyć puli.")
        connection_pool = None
        return

    logger.info(f"Inicjalizuję pulę połączeń MySQL (rozmiar: {pool_size})...")
    try:
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="waifu_pool",
            pool_size=pool_size,
            **config_data # Użyj rozpakowanego słownika
        )
        logger.info("Pula połączeń MySQL zainicjalizowana pomyślnie.")
        conn = connection_pool.get_connection()
        logger.info(f"Pomyślnie pobrano testowe połączenie z puli (ID: {conn.connection_id}).")
        conn.close()
    except mysql.connector.Error as err:
        logger.critical(f"BŁĄD KRYTYCZNY podczas inicjalizacji puli połączeń MySQL: {err}", exc_info=True)
        connection_pool = None 

def get_connection():
    """Pobiera połączenie z puli."""
    if not connection_pool:
        logger.error("Pula połączeń nie jest zainicjalizowana. Próbuję zainicjalizować teraz...")
        initialize_connection_pool()
        if not connection_pool:
             raise mysql.connector.Error("Nie udało się uzyskać połączenia - pula nie istnieje po próbie inicjalizacji.")
    try:
        conn = connection_pool.get_connection()
        logger.debug(f"Pobrano połączenie {conn.connection_id} z puli.")
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Błąd podczas pobierania połączenia z puli: {err}", exc_info=True)
        raise

def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True) 
        cursor.execute(query, params)
        if commit:
            conn.commit()
            logger.debug(f"Zapytanie wykonane z COMMIT. Rows affected: {cursor.rowcount}, Lastrowid: {cursor.lastrowid}")
            return cursor.lastrowid if cursor.lastrowid else cursor.rowcount
        elif fetch_one:
            result = cursor.fetchone()
            logger.debug(f"Zapytanie wykonane (fetch_one). Zwrócono: {'Dane' if result else 'Brak'}")
            return result
        elif fetch_all:
            result = cursor.fetchall()
            logger.debug(f"Zapytanie wykonane (fetch_all). Zwrócono: {len(result) if result else 0} wierszy.")
            return result
        return None 
    except mysql.connector.Error as err:
        logger.error(f"Błąd wykonania zapytania: {err}\nZapytanie: {query}\nParams: {params}", exc_info=True)
        if conn and commit: # Rollback tylko jeśli był błąd przy operacji z commitem
            try: conn.rollback(); logger.info("Rollback wykonany po błędzie.")
            except Exception as e_rb: logger.error(f"Błąd podczas rollback: {e_rb}")
        raise 
    finally:
        if cursor: cursor.close()
        if conn: conn.close(); logger.debug(f"Zwrócono połączenie do puli.")

def get_or_create_model(model_name):
    from utils import sanitize_foldername 
    sanitized = sanitize_foldername(model_name)
    query_select = "SELECT model_id, model_name, sanitized_name FROM models WHERE model_name = %s OR sanitized_name = %s"
    model = execute_query(query_select, (model_name, sanitized), fetch_one=True)
    if model:
        # Sprawdź, czy sanitizowana nazwa jest zgodna, jeśli nie, zaktualizuj
        if model['sanitized_name'] != sanitized and model['model_name'] == model_name:
            logger.info(f"Model '{model_name}' istnieje, ale sanitizowana nazwa się różni. Aktualizuję: '{model['sanitized_name']}' -> '{sanitized}'")
            execute_query("UPDATE models SET sanitized_name = %s WHERE model_id = %s", (sanitized, model['model_id']), commit=True)
        return model['model_id']
    else:
        logger.info(f"Tworzę nowy wpis dla modelki: {model_name} (sanitized: {sanitized})")
        query_insert = "INSERT INTO models (model_name, sanitized_name) VALUES (%s, %s)"
        try:
            return execute_query(query_insert, (model_name, sanitized), commit=True)
        except mysql.connector.IntegrityError:
            logger.warning(f"Model '{model_name}' lub '{sanitized}' już istnieje (IntegrityError po próbie insertu), próbuję pobrać ponownie.")
            model = execute_query(query_select, (model_name, sanitized), fetch_one=True)
            return model['model_id'] if model else None

def get_gallery(gallery_id):
    query = """
        SELECT g.*, m.model_name, m.sanitized_name as model_sanitized_name
        FROM galleries g
        JOIN models m ON g.model_id = m.model_id
        WHERE g.gallery_id = %s
    """
    return execute_query(query, (gallery_id,), fetch_one=True)

def get_model_galleries(model_id):
    query = "SELECT * FROM galleries WHERE model_id = %s ORDER BY gallery_id DESC" # Sortowanie może być przydatne
    return execute_query(query, (model_id,), fetch_all=True)

def update_gallery(gallery_data): # Ogólna funkcja insert/update
    query = """
        INSERT INTO galleries (gallery_id, model_id, url, original_title, determined_title,
                               folder_path, expected_count, downloaded_count, status,
                               last_processed_timestamp, error_message)
        VALUES (%(gallery_id)s, %(model_id)s, %(url)s, %(original_title)s, %(determined_title)s,
                %(folder_path)s, %(expected_count)s, %(downloaded_count)s, %(status)s,
                %(last_processed_timestamp)s, %(error_message)s)
        ON DUPLICATE KEY UPDATE
            model_id = VALUES(model_id),
            url = VALUES(url),
            original_title = COALESCE(VALUES(original_title), original_title),
            determined_title = COALESCE(VALUES(determined_title), determined_title),
            folder_path = COALESCE(VALUES(folder_path), folder_path),
            expected_count = COALESCE(VALUES(expected_count), expected_count),
            downloaded_count = VALUES(downloaded_count),
            status = VALUES(status),
            last_processed_timestamp = VALUES(last_processed_timestamp),
            error_message = VALUES(error_message),
            updated_at = NOW()
    """
    # Uzupełnij brakujące klucze domyślnymi wartościami, aby uniknąć błędów
    defaults = {
        'original_title': None, 'determined_title': None, 'folder_path': None,
        'expected_count': None, 'downloaded_count': 0, 'status': 'pending_check',
        'last_processed_timestamp': None, 'error_message': None
    }
    for key, value in defaults.items():
        gallery_data.setdefault(key, value)
        
    return execute_query(query, gallery_data, commit=True)

def update_gallery_smart(gallery_data, only_if_newer_scan_data=False):
    """
    Inteligentnie aktualizuje lub wstawia dane galerii.
    Jeśli only_if_newer_scan_data jest True, aktualizuje tylko podstawowe dane ze skanowania strony modelki
    (url, original_title, expected_count) i nie nadpisuje statusu, jeśli galeria była już przetwarzana.
    """
    existing_gallery = get_gallery(gallery_data['gallery_id'])

    if existing_gallery:
        if only_if_newer_scan_data:
            # Aktualizuj tylko jeśli nowe dane są "lepsze" lub galeria jest nowa/nieprzetworzona
            update_payload = {
                'gallery_id': gallery_data['gallery_id'],
                'model_id': gallery_data['model_id'], # Model ID raczej się nie zmienia dla galerii
                'url': gallery_data.get('url', existing_gallery['url'])
            }
            changed = False
            # Aktualizuj original_title, jeśli nowy jest inny i niepusty
            if gallery_data.get('original_title') and gallery_data['original_title'] != existing_gallery.get('original_title'):
                update_payload['original_title'] = gallery_data['original_title']
                changed = True
            else:
                update_payload['original_title'] = existing_gallery.get('original_title')

            # Aktualizuj expected_count, jeśli nowy jest większy lub stary był NULL
            new_expected = gallery_data.get('expected_count')
            old_expected = existing_gallery.get('expected_count')
            if new_expected is not None and (old_expected is None or new_expected > old_expected):
                update_payload['expected_count'] = new_expected
                changed = True
                 # Jeśli expected_count się zmienił (na większy), a galeria była 'completed', zmień status
                if existing_gallery.get('status') in ['completed', 'completed_with_tolerance']:
                    update_payload['status'] = 'pending_check' # Wymaga ponownego sprawdzenia
            else:
                 update_payload['expected_count'] = old_expected
            
            if not changed and existing_gallery.get('status') not in ['pending_check', 'error']: # Jeśli nic się nie zmieniło i status jest OK
                 logger.debug(f"Smart update dla {gallery_data['gallery_id']}: brak istotnych zmian ze skanu, nie aktualizuję.")
                 return existing_gallery['gallery_id']

            # Nie nadpisujemy statusu, downloaded_count, determined_title, folder_path itd. tymi podstawowymi danymi
            # chyba że zmiana expected_count to wymusza (jak wyżej)
            update_payload.setdefault('status', existing_gallery['status'])
            update_payload.setdefault('downloaded_count', existing_gallery['downloaded_count'])
            update_payload.setdefault('determined_title', existing_gallery['determined_title'])
            update_payload.setdefault('folder_path', existing_gallery['folder_path'])
            update_payload.setdefault('last_processed_timestamp', existing_gallery['last_processed_timestamp'])
            update_payload.setdefault('error_message', existing_gallery['error_message'])
            
            logger.info(f"Smart update (istniejąca, only_if_newer): {gallery_data['gallery_id']}")
            return update_gallery(update_payload)
        else:
            # Pełna aktualizacja, nadpisz wszystkie przekazane pola
            logger.info(f"Smart update (istniejąca, pełna): {gallery_data['gallery_id']}")
            # Upewnij się, że wszystkie pola z existing_gallery są użyte, jeśli nie ma ich w gallery_data
            merged_data = {**existing_gallery, **gallery_data}
            return update_gallery(merged_data)
    else:
        # Nowa galeria, wstaw wszystkie dane
        logger.info(f"Smart update (nowa): {gallery_data['gallery_id']}")
        # Uzupełnij domyślne wartości dla nowej galerii, jeśli brakuje
        defaults = {
            'downloaded_count': 0, 'status': 'pending_check', 'determined_title': None,
            'folder_path': None, 'last_processed_timestamp': None, 'error_message': None
        }
        final_data = {**defaults, **gallery_data}
        return update_gallery(final_data)

def get_model_galleries_for_processing(model_id, check_mode="all_or_incomplete"):
    """Pobiera galerie dla danego modelu, które wymagają przetworzenia."""
    if check_mode == "only_new_or_count_changed":
        # W tym trybie chcemy galerie, które:
        # 1. Mają status 'pending_check' (nowe lub zresetowane)
        # 2. Lub status nie jest 'completed'/'completed_with_tolerance' i expected_count > downloaded_count
        # 3. Lub expected_count uległ zmianie (trudne do śledzenia bez historii, więc upraszczamy)
        #    Po prostu bierzemy te, które nie są ukończone w 100%
        query = """
            SELECT * FROM galleries 
            WHERE model_id = %s 
            AND (
                status = 'pending_check' OR 
                (status NOT IN ('completed', 'completed_with_tolerance') AND expected_count IS NOT NULL AND downloaded_count < expected_count) OR
                (status NOT IN ('completed', 'completed_with_tolerance') AND expected_count IS NULL) 
            )
            ORDER BY gallery_id DESC
        """
    elif check_mode == "all_or_incomplete": # Domyślnie ten tryb
         query = """
            SELECT * FROM galleries 
            WHERE model_id = %s 
            AND status NOT IN ('completed', 'completed_with_tolerance')
            ORDER BY gallery_id DESC
        """
    else: # Nieznany tryb, nie rób nic
        return []
        
    return execute_query(query, (model_id,), fetch_all=True) or []


def get_incomplete_galleries_db_for_queue():
    """Pobiera dane niekompletnych galerii do dodania do kolejki."""
    query = """
        SELECT g.gallery_id, g.url, g.original_title, g.determined_title, g.expected_count, m.model_name
        FROM galleries g
        JOIN models m ON g.model_id = m.model_id
        WHERE g.status NOT IN ('completed', 'completed_with_tolerance')
          AND (g.expected_count IS NULL OR g.downloaded_count < g.expected_count)
        ORDER BY m.model_name, g.gallery_id
    """
    results = execute_query(query, fetch_all=True)
    return results if results else []


def get_app_state(key):
    query = "SELECT value_text, value_json FROM app_state WHERE key_name = %s"
    result = execute_query(query, (key,), fetch_one=True)
    if result:
        return json.loads(result['value_json']) if result['value_json'] else result['value_text']
    return None

def set_app_state(key, value):
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
    query = "SELECT queue_id, item_type, item_data, priority FROM priority_queue ORDER BY priority ASC, added_timestamp ASC"
    results = execute_query(query, fetch_all=True)
    # Zwróć pełne dane, w tym 'priority', jeśli potrzebne do debugowania
    return [
        {"type": r['item_type'], "data": json.loads(r['item_data']), "priority": r['priority'], "queue_id": r['queue_id']}
        for r in results
    ] if results else []

def save_priority_queue(queue_data): # Nadpisuje całą kolejkę
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM priority_queue") 
        if queue_data: # queue_data to lista słowników {'type': ..., 'data': ..., 'priority': ...}
            query_insert = "INSERT INTO priority_queue (item_type, item_data, priority) VALUES (%s, %s, %s)"
            params_list = []
            for index, item in enumerate(queue_data):
                # Upewnij się, że 'data' jest poprawnie zakodowane do JSON
                item_data_json = json.dumps(item['data'], ensure_ascii=False)
                # Użyj priorytetu z elementu, jeśli jest, inaczej z indeksu
                priority = item.get('priority', index * 10) 
                params_list.append((item['type'], item_data_json, priority))
            
            if params_list:
                cursor.executemany(query_insert, params_list)
        conn.commit()
        logger.info(f"Zapisano {len(queue_data)} elementów do kolejki priorytetowej w DB.")
        return True
    except mysql.connector.Error as err:
        logger.error(f"Błąd zapisu kolejki priorytetowej do DB: {err}", exc_info=True)
        if conn: conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def add_to_priority_queue_db(item_type, item_data, prepend=False):
    # Prosta implementacja - dodaje nowy element.
    # Dla 'prepend' ustawiamy niski priorytet, dla 'append' - wyższy.
    # Bardziej zaawansowane sprawdzanie duplikatów można dodać tutaj, jeśli to konieczne.
    priority = 10 if prepend else 100 # Niższy numer = wyższy priorytet
    item_data_json = json.dumps(item_data, ensure_ascii=False)
    query = """
        INSERT INTO priority_queue (item_type, item_data, priority, added_timestamp) 
        VALUES (%s, %s, %s, NOW())
    """
    try:
        # Proste sprawdzenie duplikatów dla galerii (po ID w JSON) i modeli (po nazwie)
        is_duplicate = False
        if item_type == 'gallery' and isinstance(item_data, dict) and 'id' in item_data:
            check_q = "SELECT 1 FROM priority_queue WHERE item_type = 'gallery' AND JSON_UNQUOTE(JSON_EXTRACT(item_data, '$.id')) = %s LIMIT 1"
            if execute_query(check_q, (str(item_data['id']),), fetch_one=True):
                is_duplicate = True
        elif item_type in ['scan_model', 'scan_model_refresh_only'] and isinstance(item_data, str):
            check_q = "SELECT 1 FROM priority_queue WHERE item_type = %s AND item_data = %s LIMIT 1"
            # item_data (string) jest zakodowany jako JSON string ("value") w bazie
            if execute_query(check_q, (item_type, json.dumps(item_data)), fetch_one=True):
                is_duplicate = True
        
        if is_duplicate:
            logger.info(f"Element typu '{item_type}' z danymi '{item_data}' już istnieje w kolejce priorytetowej. Nie dodaję.")
            return False

        execute_query(query, (item_type, item_data_json, priority), commit=True)
        logger.info(f"Dodano element do kolejki priorytetowej (DB): typ={item_type}, prio={priority}, dane={str(item_data)[:80]}...")
        return True
    except Exception as e:
        logger.error(f"Błąd dodawania do kolejki priorytetowej (DB): {e}", exc_info=True)
        return False

# Inicjalizacja puli przy imporcie modułu
if not connection_pool:
    initialize_connection_pool()