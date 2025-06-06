# reporting.py
import time
import db_manager #
import logging
import json 

logger = logging.getLogger(__name__)

def update_current_status(message, model="", gallery="", gallery_id=None,
                          downloaded_count=None,
                          scan_session_found_count=None,
                          expected_count=None, is_processing=False):
    status_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "message": message,
        "current_model": model,
        "current_gallery_title": gallery,
        "current_gallery_id": gallery_id,
        "current_download_count": downloaded_count,
        "scan_session_found_count": scan_session_found_count,
        "current_expected_count": expected_count,
        "is_processing": is_processing
    }
    try:
        if db_manager.update_app_state('current_status', status_data): # Poprawna nazwa
            logger.debug(f"Zaktualizowano current_status w DB: {message}")
        else:
            logger.error(f"Nie udało się zaktualizować current_status w DB (update_app_state zwróciło False).")
    except AttributeError as ae: # Dodano bardziej szczegółowe logowanie błędu atrybutu
        logger.critical(f"KRYTYCZNY BŁĄD: Atrybut 'update_app_state' nie znaleziony w module 'db_manager'. Treść błędu: {ae}", exc_info=True)
    except Exception as e:
        logger.critical(f"KRYTYCZNY BŁĄD: Nie udało się zapisać statusu do bazy danych: {e}", exc_info=True)

def generate_global_html_status(): #
    logger.debug("generate_global_html_status() jest teraz puste - dane pobierane są z DB przez PHP.")
    pass