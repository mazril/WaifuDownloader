# -*- coding: utf-8 -*-
import time
import constants
import data_manager
import utils
# Usunięto import config_handler, bo nie jest już potrzebny do hosta/portu
import logging

logger = logging.getLogger(__name__)

def update_current_status(message, model="", gallery="", gallery_id=None,
                          downloaded_count=None,
                          scan_session_found_count=None,
                          expected_count=None, is_processing=False):
    """Aktualizuje plik current_status.json."""
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
    if not data_manager.save_json_file_generic(constants.CURRENT_STATUS_FILE_PATH, status_data, indent=None):
        critical_msg = f"KRYTYCZNY BŁĄD: Nie udało się zapisać pliku statusu: {constants.CURRENT_STATUS_FILE_PATH}"
        logger.critical(critical_msg)


def build_global_status_data():
    """Buduje strukturę danych dla globalnego statusu."""
    global_data = {"models": {}}
    models_in_list = data_manager.read_model_list(constants.LIST_FILE_PATH)
    if not models_in_list:
        return global_data

    for model_name_original in models_in_list:
        model_name_sanitized = utils.sanitize_foldername(model_name_original)
        model_galleries_data = data_manager.load_model_galleries_data(model_name_sanitized)

        global_data["models"][model_name_original] = {
            "galleries": {},
            "sanitized_name": model_name_sanitized # Dodajemy sanitizowaną nazwę dla PHP/JS
        }

        for gallery_id, gallery_info_from_json in model_galleries_data.items():
            if not isinstance(gallery_info_from_json, dict):
                logger.warning(f"BUILD_STATUS: Oczekiwano słownika dla gallery_id '{gallery_id}' w modelu '{model_name_original}', otrzymano {type(gallery_info_from_json)}. Pomijam.")
                continue

            is_complete = gallery_info_from_json.get("status") in ["completed", "completed_with_tolerance"]
            dl_count = gallery_info_from_json.get("downloaded_count", 0)
            expected = gallery_info_from_json.get("expected_count", None)
            status_color = "green" if is_complete else ("orange" if dl_count > 0 else "red")

            title_val = gallery_info_from_json.get("determined_title",
                            gallery_info_from_json.get("original_title_from_list",
                                str(gallery_id if gallery_id is not None else "")))

            global_data["models"][model_name_original]["galleries"][gallery_id] = {
                "title": str(title_val if title_val is not None else ""),
                "folder": gallery_info_from_json.get("folder_path_on_disk", "Brak"),
                "expected": expected,
                "downloaded": dl_count,
                "url": gallery_info_from_json.get("url", "#"),
                "status_color": status_color,
                "completed": is_complete,
                "model_name": model_name_original,
                "gallery_id": gallery_id
            }
    return global_data

def generate_global_html_status():
    """Generuje tylko plik status_aggregate.json."""
    logger.debug("Rozpoczynam generowanie status_aggregate.json...")
    data = build_global_status_data()
    logger.debug(f"Dane dla status_aggregate.json zbudowane, liczba modeli: {len(data.get('models', {}))}")

    # Zapisujemy tylko JSON, bez generowania HTML
    if data_manager.save_json_file_generic(constants.STATUS_JSON_AGGREGATE_PATH, data):
         logger.info(f"Wygenerowano plik agregacji statusu: {constants.STATUS_JSON_AGGREGATE_PATH}")
    else:
         logger.error(f"Błąd zapisu pliku agregacji statusu: {constants.STATUS_JSON_AGGREGATE_PATH}")