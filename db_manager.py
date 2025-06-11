# db_manager.py
# -*- coding: utf-8 -*-
import mysql.connector
from mysql.connector import pooling, errorcode 
import logging
import time
import config_handler 
import json

logger = logging.getLogger(__name__)

connection_pool = None

def _get_db_config_from_handler():
    if config_handler.current_config is None: 
        logger.warning("config_handler.current_config jest None. Próbuję załadować konfigurację.")
        config_handler.load_config(force_reload=True) 
        if config_handler.current_config is None: 
            logger.error("Nie udało się załadować konfiguracji z config_handler.")
            return {}, 0 

    cfg = config_handler.current_config 
    db_cfg_from_handler = cfg.get("database", {})
    
    db_details = {
        'host': db_cfg_from_handler.get('host', {}).get('value', 'localhost'),
        'user': db_cfg_from_handler.get('user', {}).get('value', 'root'),
        'password': db_cfg_from_handler.get('password', {}).get('value', ''),
        'database': db_cfg_from_handler.get('database', {}).get('value', 'waifudownloader'),
        'port': db_cfg_from_handler.get('port', {}).get('value', 3306),
        'auth_plugin': 'mysql_native_password' 
    }
    pool_size_from_handler = db_cfg_from_handler.get('pool_size', {}).get('value', 5)
    return db_details, pool_size_from_handler

def initialize_connection_pool(): 
    global connection_pool 
    if connection_pool:
        try:
            conn_test = connection_pool.get_connection()
            conn_test.close()
            logger.debug("Pula połączeń MySQL już istnieje i działa.")
            return
        except mysql.connector.Error as pool_error:
            logger.warning(f"Pula połączeń MySQL istnieje, ale wystąpił błąd przy pobieraniu połączenia: {pool_error}. Inicjalizuję ponownie.")
            connection_pool = None 
    
    db_config_values, pool_size = _get_db_config_from_handler()

    if not db_config_values.get('database') or not db_config_values.get('user'): 
        logger.critical("Brak pełnej konfiguracji bazy danych (database, user) w config.json! Nie można utworzyć puli.")
        connection_pool = None 
        return

    logger.info(f"Inicjalizuję pulę połączeń MySQL (Host: {db_config_values['host']}, DB: {db_config_values['database']}, Rozmiar: {pool_size})...")
    try:
        connection_pool = pooling.MySQLConnectionPool(
            pool_name="waifu_pool",
            pool_size=pool_size,
            pool_reset_session=True, 
            **db_config_values
        )
        logger.info("Pula połączeń MySQL została zainicjalizowana pomyślnie.")
        conn = connection_pool.get_connection()
        logger.info(f"Pomyślnie pobrano testowe połączenie z puli (ID: {conn.connection_id}).")
        conn.close()
    except mysql.connector.Error as err:
        logger.error(f"Błąd inicjalizacji puli połączeń MySQL: {err}", exc_info=True)
        connection_pool = None 
    except Exception as e: 
        logger.error(f"Nieoczekiwany błąd podczas inicjalizacji puli połączeń: {e}", exc_info=True)
        connection_pool = None

def get_connection(): 
    global connection_pool 
    if not connection_pool:
        logger.warning("Pula połączeń MySQL nie jest zainicjalizowana. Próbuję zainicjalizować...")
        initialize_connection_pool()
        if not connection_pool: 
            logger.error("Nie udało się uzyskać połączenia - brak puli po próbie inicjalizacji.")
            return None 
    try:
        return connection_pool.get_connection()
    except mysql.connector.Error as err:
        logger.error(f"Błąd pobierania połączenia z puli MySQL: {err}", exc_info=True)
        if err.errno == errorcode.CR_CONN_HOST_ERROR or \
           err.errno == errorcode.CR_SERVER_GONE_ERROR:
            logger.warning("Podejrzewany problem z połączeniem/serwerem. Próbuję zresetować pulę.")
            connection_pool = None 
        return None
    except Exception as e: 
        logger.error(f"Nieoczekiwany błąd podczas pobierania połączenia z puli: {e}", exc_info=True)
        return None

def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False, attempts=3, delay=5): 
    last_exception = None
    for attempt in range(attempts):
        connection = get_connection()
        if not connection:
            logger.error(f"Pominięto próbę {attempt + 1} wykonania zapytania z powodu braku połączenia z DB.")
            if attempt < attempts - 1: time.sleep(delay)
            last_exception = mysql.connector.Error("Nie udało się uzyskać połączenia z puli DB.")
            continue

        cursor = None
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            
            if commit:
                connection.commit()
                logger.debug(f"Zapytanie (commit) wykonane pomyślnie. Lastrowid: {cursor.lastrowid}, Rowcount: {cursor.rowcount}")
                return True 
            elif fetch_one:
                result = cursor.fetchone()
                logger.debug(f"Zapytanie (fetch_one) wykonane. Wynik: {'Jest' if result else 'Brak'}")
                return result
            elif fetch_all:
                result = cursor.fetchall()
                logger.debug(f"Zapytanie (fetch_all) wykonane. Liczba wierszy: {len(result) if result else 0}")
                return result
            else: 
                 logger.debug("Zapytanie wykonane bez commit/fetch.")
                 return None 
        
        except mysql.connector.Error as err:
            logger.warning(f"Błąd MySQL (próba {attempt + 1}/{attempts}): {err.errno} - {err.msg}. Zapytanie: {query[:500]}... Params: {params}")
            last_exception = err
            if connection: 
                try:
                    if connection.in_transaction: 
                        connection.rollback()
                        logger.info("Rollback wykonany po błędzie w zapytaniu.")
                except mysql.connector.Error as rb_err:
                    logger.error(f"Błąd podczas rollback: {rb_err}")
            
            if err.errno in [errorcode.CR_SERVER_GONE_ERROR, 
                             errorcode.CR_SERVER_LOST,
                             errorcode.CR_CONN_HOST_ERROR]: 
                logger.warning("Wykryto błąd utraty połączenia z serwerem MySQL. Resetuję pulę połączeń.")
                global connection_pool
                connection_pool = None 

            if attempt < attempts - 1: time.sleep(delay * (attempt + 1))
        
        finally:
            if cursor: cursor.close()
            if connection: connection.close() 
    
    logger.error(f"Nie udało się wykonać zapytania po {attempts} próbach. Ostatni błąd: {last_exception}. Zapytanie: {query[:500]}...")
    if isinstance(last_exception, mysql.connector.Error):
        logger.error(f"Szczegóły ostatniego błędu MySQL: Kod {last_exception.errno}, Wiadomość: {last_exception.msg}") 
    return None 

def get_or_create_model(model_name): 
    import utils 
    sanitized = utils.sanitize_foldername(model_name) 
    query_select = "SELECT model_id, model_name, sanitized_name FROM models WHERE model_name = %s OR sanitized_name = %s"
    model_data = execute_query(query_select, (model_name, sanitized), fetch_one=True)
    if model_data:
        if model_data['model_name'] == model_name and model_data['sanitized_name'] != sanitized:
            logger.info(f"Model '{model_name}' istnieje (ID: {model_data['model_id']}), aktualizuję sanitized_name: '{model_data['sanitized_name']}' -> '{sanitized}'")
            execute_query("UPDATE models SET sanitized_name = %s WHERE model_id = %s", (sanitized, model_data['model_id']), commit=True)
        elif model_data['sanitized_name'] == sanitized and model_data['model_name'] != model_name:
             logger.info(f"Model ze znormalizowaną nazwą '{sanitized}' istnieje (ID: {model_data['model_id']}), aktualizuję model_name: '{model_data['model_name']}' -> '{model_name}'")
             execute_query("UPDATE models SET model_name = %s WHERE model_id = %s", (model_name, model_data['model_id']), commit=True)
        return model_data['model_id']
    else:
        logger.info(f"Tworzę nowy wpis dla modelki: {model_name} (sanitized: {sanitized})")
        query_insert = "INSERT INTO models (model_name, sanitized_name) VALUES (%s, %s)"
        insert_success = execute_query(query_insert, (model_name, sanitized), commit=True)
        
        if insert_success:
            model_data_after_insert = execute_query(query_select, (model_name, sanitized), fetch_one=True)
            if model_data_after_insert:
                logger.info(f"Utworzono model '{model_name}' z ID: {model_data_after_insert['model_id']}")
                return model_data_after_insert['model_id']
            else:
                logger.error(f"Nie udało się pobrać ID dla nowo wstawionego modelu '{model_name}'.")
                return None
        else:
            logger.warning(f"Nie udało się wstawić modelu '{model_name}'. Sprawdzam, czy już istnieje (race condition?).")
            model_data_retry = execute_query(query_select, (model_name, sanitized), fetch_one=True)
            if model_data_retry:
                logger.info(f"Model '{model_name}' już istniał (ID: {model_data_retry['model_id']}).")
                return model_data_retry['model_id']
            else:
                logger.error(f"Ostatecznie nie udało się uzyskać/stworzyć ID dla modelu '{model_name}'.")
                return None

def get_gallery(gallery_id):
    raw_result = execute_query("SELECT g.*, m.model_name, m.sanitized_name FROM galleries g JOIN models m ON g.model_id = m.model_id WHERE g.gallery_id = %s", (gallery_id,), fetch_one=True)
    return raw_result

def get_model_galleries(model_id): 
    query = "SELECT * FROM galleries WHERE model_id = %s AND is_disabled = FALSE ORDER BY gallery_id DESC" 
    return execute_query(query, (model_id,), fetch_all=True)

def update_gallery(gallery_id, **kwargs):
    """
    Aktualizuje określone kolumny dla danej galerii w bazie danych.
    
    Opis modyfikacji:
    - Dodano `is_disabled` do listy `valid_columns`, aby umożliwić
      aktualizację tej flagi.
      
    Wpływ na inne funkcje:
    - Umożliwia `processing.py` i `api.php` włączanie/wyłączanie galerii.
    """
    if not kwargs:
        logger.warning(f"Wywołano update_gallery bez żadnych argumentów do aktualizacji dla {gallery_id}.")
        return False 
    valid_columns = [
        'model_id', 'url', 'original_title', 'source_page_title', 
        'determined_title', 'test_ai_title', 'folder_path', 'expected_count', 
        'downloaded_count', 'status', 'tags_json', 'initial_data_fetched',
        'last_checked', 'last_downloaded', 'last_processed_timestamp', 'error_message', 'gallery_description',
        'links_collected', 'image_links_json', 'is_disabled'
    ]
    set_clauses = []
    params = []
    for key, value in kwargs.items():
        if key in valid_columns:
            set_clauses.append(f"`{key}` = %s") 
            if key in ['initial_data_fetched', 'links_collected', 'is_disabled'] and isinstance(value, bool):
                params.append(1 if value else 0) 
            elif key in ['tags_json', 'image_links_json'] and isinstance(value, (dict, list)):
                 params.append(json.dumps(value, ensure_ascii=False))
            else:
                params.append(value)
        else:
            logger.warning(f"Próba aktualizacji nieznanej lub niedozwolonej kolumny '{key}' w update_gallery dla {gallery_id}.")
    if not set_clauses:
        logger.warning(f"Brak poprawnych pól do aktualizacji w update_gallery dla {gallery_id}.")
        return False 
    set_clauses.append("`updated_at` = NOW()") 
    query = f"UPDATE `galleries` SET {', '.join(set_clauses)} WHERE `gallery_id` = %s"
    params.append(gallery_id) 
    params_to_log = []
    for p_val in params[:-1]: 
        if isinstance(p_val, str) and len(p_val) > 100:
            params_to_log.append(p_val[:100] + "...")
        else:
            params_to_log.append(p_val)
    logger.info(f"Aktualizuję galerię {gallery_id}: Pola: {list(kwargs.keys())} | Wartości (częściowe): {params_to_log}")
    return execute_query(query, tuple(params), commit=True)

def update_gallery_smart(gallery_data, only_if_newer_scan_data=False): 
    gallery_id = gallery_data.get("gallery_id")
    if not gallery_id:
        logger.error("Brak gallery_id w danych dla update_gallery_smart.")
        return False 
    
    existing_gallery = get_gallery(gallery_id)
    
    if existing_gallery:
        updates_to_perform = {}
        if 'url' in gallery_data and gallery_data['url'] != existing_gallery.get('url'):
            updates_to_perform['url'] = gallery_data['url']
        
        if 'original_title' in gallery_data and gallery_data['original_title'] and \
           (not existing_gallery.get('original_title') or not only_if_newer_scan_data):
            updates_to_perform['original_title'] = gallery_data['original_title']
        
        new_expected = gallery_data.get('expected_count')
        if new_expected is not None: 
            if existing_gallery.get('expected_count') is None or new_expected > existing_gallery.get('expected_count', 0):
                 updates_to_perform['expected_count'] = new_expected
            elif not only_if_newer_scan_data and new_expected < existing_gallery.get('expected_count', 0): 
                 updates_to_perform['expected_count'] = new_expected
        
        if 'last_checked' in gallery_data:
             updates_to_perform['last_checked'] = gallery_data['last_checked']
        elif updates_to_perform: 
             updates_to_perform['last_checked'] = time.strftime('%Y-%m-%d %H:%M:%S')

        if 'status' in gallery_data and \
            (not only_if_newer_scan_data or \
             (gallery_data['status'] == 'pending_check' and existing_gallery.get('status') != 'pending_check')):
             updates_to_perform['status'] = gallery_data['status']
        
        if 'initial_data_fetched' in gallery_data:
            new_idf_value = gallery_data['initial_data_fetched']
            if isinstance(new_idf_value, bool):
                updates_to_perform['initial_data_fetched'] = new_idf_value
            else:
                logger.warning(f"Niepoprawny typ dla initial_data_fetched w update_gallery_smart (istniejąca): {type(new_idf_value)}. Oczekiwano bool.")
        
        if 'source_page_title' in gallery_data: 
            updates_to_perform['source_page_title'] = gallery_data['source_page_title']
        if 'tags_json' in gallery_data: 
            updates_to_perform['tags_json'] = gallery_data['tags_json']

        if updates_to_perform:
            logger.info(f"update_gallery_smart dla {gallery_id}: Wykonuję aktualizacje: {list(updates_to_perform.keys())}")
            return update_gallery(gallery_id, **updates_to_perform)
        else:
            logger.debug(f"Galeria {gallery_id} nie wymagała aktualizacji (update_gallery_smart).")
            return True
    else: 
        logger.info(f"Wstawiam nową galerię do DB (przez update_gallery_smart): {gallery_id}")
        
        columns_for_insert = [
            'gallery_id', 'model_id', 'url', 'original_title', 'expected_count', 'status', 
            'initial_data_fetched', 'downloaded_count', 'source_page_title', 
            'determined_title', 'test_ai_title', 'folder_path', 'tags_json',
            'last_checked', 'gallery_description', 'is_disabled'
        ]
        
        values_dict = {
            'gallery_id': gallery_data.get('gallery_id'),
            'model_id': gallery_data.get('model_id'), 'url': gallery_data.get('url'),
            'original_title': gallery_data.get('original_title'),
            'expected_count': gallery_data.get('expected_count'), 
            'status': gallery_data.get('status', 'pending_check'), 
            'initial_data_fetched': gallery_data.get('initial_data_fetched', False), 
            'downloaded_count': gallery_data.get('downloaded_count', 0), 
            'source_page_title': gallery_data.get('source_page_title'), 'determined_title': gallery_data.get('determined_title'), 
            'test_ai_title': gallery_data.get('test_ai_title'), 'folder_path': gallery_data.get('folder_path'),           
            'tags_json': json.dumps(gallery_data.get('tags_json'), ensure_ascii=False) if gallery_data.get('tags_json') else None, 
            'last_checked': gallery_data.get('last_checked', time.strftime('%Y-%m-%d %H:%M:%S')),
            'gallery_description': gallery_data.get('gallery_description'),
            'is_disabled': gallery_data.get('is_disabled', False)
        }
        
        final_columns_for_insert, final_values_placeholders, final_values_params = [], [], []
        
        actual_db_columns = None
        try:
            sample_gallery = execute_query("SELECT * FROM galleries LIMIT 1", fetch_one=True)
            if sample_gallery: actual_db_columns = list(sample_gallery.keys())
        except Exception as e_cols: logger.warning(f"Nie udało się pobrać rzeczywistych nazw kolumn z tabeli galleries: {e_cols}")

        for col_name in columns_for_insert:
            if actual_db_columns and col_name not in actual_db_columns:
                logger.warning(f"Kolumna '{col_name}' zdefiniowana w kodzie nie istnieje w tabeli 'galleries'. Pomijam przy INSERT.")
                continue

            current_val_for_insert = values_dict.get(col_name)
            if current_val_for_insert is not None or col_name in ['initial_data_fetched', 'is_disabled']:
                final_columns_for_insert.append(f"`{col_name}`")
                final_values_placeholders.append('%s')
                val_to_append = current_val_for_insert
                if col_name in ['initial_data_fetched', 'is_disabled'] and current_val_for_insert is None: 
                    val_to_append = False 
                if isinstance(val_to_append, bool): final_values_params.append(1 if val_to_append else 0)
                else: final_values_params.append(val_to_append)
        
        if not final_columns_for_insert: 
            logger.error(f"Brak danych do wstawienia dla nowej galerii {gallery_id} w update_gallery_smart.")
            return False

        query = f"INSERT INTO galleries ({', '.join(final_columns_for_insert)}) VALUES ({', '.join(final_values_placeholders)})"
        return execute_query(query, tuple(final_values_params), commit=True)

def get_model_galleries_for_processing(model_id, check_mode="all_or_incomplete"):
    """
    Pobiera galerie modelu do przetworzenia, ignorując te, które są wyłączone.
    
    Opis modyfikacji:
    - Dodano warunek `AND g.is_disabled = FALSE` do wszystkich zapytań,
      aby skrypt nie próbował ponownie przetwarzać wyłączonych galerii.
      
    Wpływ na inne funkcje:
    - Główna pętla w `processing.py` będzie teraz automatycznie pomijać
      wyłączone galerie.
    """
    base_query = "SELECT * FROM galleries g WHERE g.model_id = %s AND g.is_disabled = FALSE"
    conditions = []
    statuses_final = "('completed', 'completed_with_tolerance', 'disabled_bad_links')"
    statuses_ai_cycle = "('pending_production_ai', 'pending_test_ai', 'pending_initial_fetch_prod_ai', 'pending_initial_fetch_test_ai', 'test_completed', 'error_ai_prod', 'error_ai_test', 'error_ai')"
    statuses_to_retry_later = "('partially_downloaded', 'downloaded_unknown_total')"

    if check_mode == "only_new_or_count_changed":
        conditions.append(f"""
            (initial_data_fetched = FALSE OR links_collected = FALSE OR status = 'pending_check' OR status = 'error')
             AND status NOT IN {statuses_to_retry_later} AND status NOT IN {statuses_ai_cycle}
        """)
    elif check_mode == "all_or_incomplete":
        conditions.append(f"status NOT IN {statuses_final} AND status NOT IN {statuses_ai_cycle} AND status NOT IN {statuses_to_retry_later}")
    elif check_mode == "fill_incomplete_only":
        conditions.append(f"status IN {statuses_to_retry_later}")
    else:
        logger.warning(f"Nieznany check_mode: {check_mode} w get_model_galleries_for_processing.")
        return []
    
    query = f"{base_query} AND ({' OR '.join(conditions)}) ORDER BY original_title ASC, gallery_id DESC"
    logger.info(f"Zapytanie dla get_model_galleries_for_processing (model_id: {model_id}, mode: {check_mode}): {query % (model_id,)}") 
    return execute_query(query, (model_id,), fetch_all=True) or []


def get_ready_to_download_galleries_for_model(model_id):
    """
    Pobiera galerie dla danego modelu, które są gotowe do pobrania plików.
    
    Opis:
    - Nowa funkcja pomocnicza.
    - Wyszukuje galerie, które mają już tytuł od AI (`determined_title`)
      oraz zebrane linki (`links_collected = TRUE`), ale nie są jeszcze
      ukończone.
      
    Wpływ na inne funkcje:
    - Wywoływana z `processing.py` w `handle_process_models`, aby umożliwić
      oportunistyczne pobieranie galerii, gdy tylko będą gotowe.
    """
    query = """
        SELECT * FROM galleries 
        WHERE model_id = %s 
          AND is_disabled = FALSE
          AND determined_title IS NOT NULL
          AND links_collected = TRUE
          AND status NOT IN ('completed', 'completed_with_tolerance', 'partially_downloaded', 'downloaded_unknown_total', 'disabled_bad_links')
        ORDER BY original_title ASC, gallery_id DESC
    """
    return execute_query(query, (model_id,), fetch_all=True) or []

def get_incomplete_galleries_db_for_queue(): 
    statuses_definitely_complete = "('completed', 'completed_with_tolerance', 'disabled_bad_links')" 
    statuses_ai_cycle_to_exclude = "('pending_production_ai', 'pending_test_ai', 'pending_initial_fetch_prod_ai', 'pending_initial_fetch_test_ai', 'test_completed', 'error_ai_test', 'error_ai_prod', 'error_ai')"
    query = f"""
        SELECT g.gallery_id, g.url, g.original_title, g.determined_title, g.expected_count, m.model_name
        FROM galleries g
        JOIN models m ON g.model_id = m.model_id
        WHERE 
          g.is_disabled = FALSE AND (
            (g.initial_data_fetched = FALSE OR g.status = 'pending_check' OR g.status = 'error' OR g.links_collected = FALSE) OR 
            (g.status NOT IN {statuses_definitely_complete} AND 
             g.status NOT IN {statuses_ai_cycle_to_exclude} AND
             (g.expected_count IS NULL OR g.downloaded_count < g.expected_count)
            )
          )
        ORDER BY m.model_name, g.gallery_id
    """
    results = execute_query(query, fetch_all=True)
    return results if results else []

def get_app_state(key_name): 
    result = execute_query("SELECT value_json FROM app_state WHERE key_name = %s", (key_name,), fetch_one=True)
    if result and result.get('value_json'):
        try:
            return json.loads(result['value_json'])
        except json.JSONDecodeError:
            logger.error(f"Błąd dekodowania JSON dla klucza app_state: {key_name}")
            return None
    return None

def update_app_state(key_name, value): 
    value_json = json.dumps(value, ensure_ascii=False)
    query = """
        INSERT INTO app_state (key_name, value_json, updated_at) 
        VALUES (%s, %s, NOW())
        ON DUPLICATE KEY UPDATE 
            value_json = VALUES(value_json), 
            updated_at = NOW()
    """
    return execute_query(query, (key_name, value_json), commit=True)

def get_priority_queue(): 
    results = execute_query("SELECT item_type, item_data, priority FROM priority_queue ORDER BY priority ASC, added_timestamp ASC", fetch_all=True)
    queue = []
    if results:
        for row in results:
            try:
                item_data_str = row['item_data']
                item_data = {}
                if item_data_str:
                    try:
                        item_data = json.loads(item_data_str)
                    except json.JSONDecodeError as jd_err:
                        logger.error(f"Błąd dekodowania JSON dla elementu kolejki (item_data: '{item_data_str}'): {jd_err}")
                        item_data = {"raw_data": item_data_str, "decode_error": str(jd_err)}

                queue.append({"type": row['item_type'], 
                              "payload": item_data,
                              "priority": row.get('priority')}) 
            except Exception as e_pq: 
                logger.error(f"Błąd przetwarzania wiersza kolejki: {row}. Błąd: {e_pq}")
    return queue

def save_priority_queue(queue_data): 
    connection = get_connection()
    if not connection: return False
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM priority_queue") 
        if queue_data: 
            sql = "INSERT INTO priority_queue (item_type, item_data, priority, added_timestamp) VALUES (%s, %s, %s, NOW())"
            params_list = []
            for index, item in enumerate(queue_data):
                item_data_to_save = item.get('payload', {}) 
                item_data_json = json.dumps(item_data_to_save, ensure_ascii=False)
                priority = item.get('priority', index * 10) 
                
                params_list.append((item['type'], item_data_json, priority))
            if params_list: 
                cursor.executemany(sql, params_list)
        connection.commit()
        logger.debug(f"Zapisano {len(queue_data)} elementów do kolejki priorytetowej w DB.")
        return True
    except mysql.connector.Error as err:
        logger.error(f"Błąd zapisu kolejki do DB: {err}")
        if connection and connection.in_transaction: 
            connection.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

def get_ai_prompt_config_from_db(config_id='production'): 
    sql = """
        SELECT config_id, system_prompt, ollama_model_name, ollama_temperature, 
               ollama_num_predict, ollama_top_p, description
        FROM ai_prompt_configs 
        WHERE config_id = %s
    """
    config = execute_query(sql, (config_id,), fetch_one=True)
    if not config:
        logger.error(f"Nie znaleziono konfiguracji promptu AI o ID: '{config_id}' w bazie danych.")
        if config_id != "production": 
            logger.warning(f"Próbuję załadować konfigurację 'production' jako fallback dla '{config_id}'.")
            return get_ai_prompt_config_from_db("production") 
        return None 
    logger.info(f"Pomyślnie pobrano konfigurację promptu AI '{config_id}' z bazy danych.")
    return config

def add_to_priority_queue(item_type, item_data, add_to_front=False):
    current_queue = get_priority_queue() 
    new_item = {"type": item_type, "payload": item_data} 

    item_id_to_check = None
    if isinstance(item_data, dict):
        item_id_to_check = item_data.get("id")
    elif isinstance(item_data, str) and item_type in ['scan_model', 'scan_model_refresh_only']:
        item_id_to_check = item_data 

    is_duplicate = False
    if item_id_to_check:
        for item in current_queue:
            payload_in_queue = item.get('payload', {})
            type_in_queue = item.get('type')

            if type_in_queue == item_type:
                if isinstance(payload_in_queue, dict) and payload_in_queue.get("id") == item_id_to_check:
                    is_duplicate = True
                    break
                elif isinstance(payload_in_queue, str) and payload_in_queue == item_id_to_check: 
                    is_duplicate = True
                    break
    
    if is_duplicate:
        logger.info(f"Element typu '{item_type}' z ID/danymi '{item_id_to_check}' już istnieje w kolejce (db_manager.add_to_priority_queue). Nie dodaję.")
        return False 
    
    if add_to_front:
        current_queue.insert(0, new_item)
        logger.info(f"Dodano element na POCZĄTEK kolejki (db_manager): {new_item}")
    else:
        current_queue.append(new_item)
        logger.info(f"Dodano element na KONIEC kolejki (db_manager): {new_item}")
    
    for index, item in enumerate(current_queue):
        item['priority'] = index * 10 
    
    return save_priority_queue(current_queue)