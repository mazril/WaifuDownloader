# -*- coding: utf-8 -*-
import time
import constants
import db_manager # Zamiast data_manager do zapisu statusu
import logging

logger = logging.getLogger(__name__)

def update_current_status(message, model="", gallery="", gallery_id=None,
                          downloaded_count=None,
                          scan_session_found_count=None,
                          expected_count=None, is_processing=False):
    """Aktualizuje status w tabeli app_state w bazie danych."""
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
        db_manager.set_app_state('current_status', status_data)
        logger.debug(f"Zaktualizowano current_status w DB: {message}")
    except Exception as e:
        logger.critical(f"KRYTYCZNY BŁĄD: Nie udało się zapisać statusu do bazy danych: {e}", exc_info=True)


# Usunięto build_global_status_data() i generate_global_html_status()
# Te dane będą teraz pobierane bezpośrednio przez PHP z bazy danych.

def generate_global_html_status():
    """
    Ta funkcja nie jest już potrzebna w tej formie.
    PHP będzie pobierać dane bezpośrednio z bazy.
    Możemy ją zostawić pustą lub usunąć. Zostawiamy pustą dla zgodności.
    """
    logger.debug("generate_global_html_status() jest teraz puste - dane pobierane są z DB przez PHP.")
    pass