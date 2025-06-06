# -*- coding: utf-8 -*-
import os
import subprocess
import logging
import config_handler  # Używamy istniejącego handlera konfiguracji

# Prosta konfiguracja logowania, aby wyświetlać komunikaty w konsoli
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-8s] %(message)s')
logger = logging.getLogger(__name__)

# --- Konfiguracja ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILENAME = "struktura_bazy_danych.txt"
OUTPUT_FILE_PATH = os.path.join(SCRIPT_DIR, OUTPUT_FILENAME)

# WAŻNE: Dostosuj tę ścieżkę, jeśli mysqldump.exe znajduje się w innym miejscu
# lub jeśli nie jest dodany do zmiennej środowiskowej PATH w Twoim systemie.
# Ta ścieżka została pobrana z Twojego pliku backup_manager.py
MYSQLDUMP_PATH = r"C:\xampp\mysql\bin\mysqldump.exe"

def generuj_strukture_bazy():
    """
    Generuje plik tekstowy ze strukturą tabel bazy danych, korzystając z mysqldump.
    Logika została zaadaptowana ze skryptu backup_manager.py.
    """
    logger.info(f"Rozpoczynam generowanie pliku struktury bazy danych do: {OUTPUT_FILE_PATH}")

    # 1. Załaduj konfigurację bazy danych z pliku config.json
    try:
        config_handler.load_config(force_reload=True)
        db_config = config_handler.current_config.get("database")
        if not db_config or not all(db_config.get(k, {}).get("value") for k in ["host", "user", "database"]):
            logger.error("Konfiguracja bazy danych w config.json jest niekompletna. Przerywam.")
            return False
    except Exception as e:
        logger.error(f"Błąd ładowania konfiguracji bazy danych: {e}", exc_info=True)
        return False

    # 2. Pobierz dane dostępowe do bazy
    db_host = db_config["host"]["value"]
    db_user = db_config["user"]["value"]
    db_password = db_config.get("password", {}).get("value", "")
    db_name = db_config["database"]["value"]
    db_port = str(db_config.get("port", {}).get("value", 3306))

    # 3. Zbuduj polecenie mysqldump z odpowiednimi flagami
    command = [
        MYSQLDUMP_PATH,
        f"--host={db_host}",
        f"--port={db_port}",
        f"--user={db_user}"
    ]
    if db_password:
        command.append(f"--password={db_password}")

    # Flagi, aby zrzucić tylko strukturę (CREATE TABLE), bez danych i dodatkowych obiektów
    command.extend([
        "--no-data",          # Nie dołączaj danych z tabel
        "--skip-triggers",    # Pomiń triggery
        "--skip-routines",    # Pomiń procedury i funkcje
        "--skip-events",      # Pomiń zdarzenia
        db_name               # Nazwa bazy danych do zrzucenia
    ])

    # 4. Wykonaj polecenie i zapisz wynik do pliku
    process = None
    file_handle = None
    try:
        file_handle = open(OUTPUT_FILE_PATH, 'w', encoding='utf-8')
        
        logger.debug(f"Wykonywanie polecenia: {' '.join(command)}")
        process = subprocess.Popen(command, stdout=file_handle, stderr=subprocess.PIPE, shell=False)
        
        # Odczytaj komunikaty błędów (jeśli wystąpią)
        stderr_output_bytes, _ = process.communicate()
        stderr_output = stderr_output_bytes.decode(errors='replace') if stderr_output_bytes else ""

        if process.returncode == 0:
            logger.info(f"Plik struktury bazy danych '{OUTPUT_FILENAME}' został pomyślnie utworzony.")
            if stderr_output:
                logger.warning(f"Komunikaty z mysqldump (stderr):\n{stderr_output}")
            return True
        else:
            error_message = f"Błąd podczas wykonywania mysqldump (kod: {process.returncode})."
            if stderr_output:
                error_message += f"\nKomunikat błędu mysqldump:\n{stderr_output}"
            logger.error(error_message)
            return False
            
    except FileNotFoundError:
        logger.error(f"Nie znaleziono programu mysqldump. Sprawdź ścieżkę: '{MYSQLDUMP_PATH}'.")
        return False
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd podczas generowania pliku struktury: {e}", exc_info=True)
        return False
    finally:
        if file_handle:
            file_handle.close()
        # Usuń plik, jeśli operacja się nie powiodła, aby nie zostawiać pustego/niekompletnego pliku
        if process and process.returncode != 0 and os.path.exists(OUTPUT_FILE_PATH):
            try:
                os.remove(OUTPUT_FILE_PATH)
            except OSError as e_rem:
                logger.error(f"Nie udało się usunąć niekompletnego pliku {OUTPUT_FILE_PATH}: {e_rem}")

if __name__ == "__main__":
    generuj_strukture_bazy()