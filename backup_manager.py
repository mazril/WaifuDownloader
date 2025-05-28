# -*- coding: utf-8 -*-
import os
import sys
import shutil
import zipfile
import datetime
import subprocess
import logging

# Dodaj ścieżkę do katalogu nadrzędnego, aby importować moduły aplikacji
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config_handler # Do odczytu konfiguracji bazy danych
# constants.py nie jest tu bezpośrednio potrzebny, bo odczytujemy config

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-8s] %(message)s')
logger = logging.getLogger(__name__)

# --- Konfiguracja Backup-u ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR_NAME = "_backups"
BACKUP_BASE_PATH = os.path.join(SCRIPT_DIR, BACKUP_DIR_NAME)

# ŚCIEŻKA DO MYSQLDUMP - dostosuj, jeśli nie jest w PATH!
# Przykład dla XAMPP: MYSQLDUMP_PATH = r"C:\xampp\mysql\bin\mysqldump.exe"
MYSQLDUMP_PATH = "mysqldump" # Zakłada, że mysqldump jest w PATH

# Pliki do dołączenia do archiwum (rozszerzenia)
FILES_TO_BACKUP_EXTENSIONS = ['.py', '.php', '.json', '.crx', '.txt']
# Pliki/foldery do zignorowania przy tworzeniu archiwum plików
FILES_TO_IGNORE = [
    BACKUP_DIR_NAME,
    "__pycache__",
    ".git",
    ".vscode",
    "script.log", # Plik logu głównego skryptu
    "backup_manager.log", # Plik logu tego skryptu
    # Możesz dodać więcej plików/folderów do ignorowania
    "Modelki" # Zazwyczaj nie chcemy backupować całego folderu Modelki z plikami
]

def create_backup_directory():
    """Tworzy katalog na backupy, jeśli nie istnieje."""
    if not os.path.exists(BACKUP_BASE_PATH):
        try:
            os.makedirs(BACKUP_BASE_PATH)
            logger.info(f"Utworzono katalog na backupy: {BACKUP_BASE_PATH}")
        except OSError as e:
            logger.error(f"Nie udało się utworzyć katalogu na backupy {BACKUP_BASE_PATH}: {e}")
            return False
    return True

def backup_program_files():
    """Tworzy archiwum ZIP z plikami programu."""
    if not create_backup_directory():
        return False

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"program_files_backup_{timestamp}.zip"
    archive_path = os.path.join(BACKUP_BASE_PATH, archive_name)

    logger.info(f"Rozpoczynam backup plików programu do: {archive_path}")
    try:
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(SCRIPT_DIR):
                # Ignorowanie określonych folderów
                dirs[:] = [d for d in dirs if d not in FILES_TO_IGNORE and not d.startswith('.')]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # Sprawdź, czy plik nie jest samym archiwum backupu lub w ignorowanym folderze
                    if file_path == archive_path or any(ignored_item in file_path for ignored_item in FILES_TO_IGNORE):
                        continue

                    # Sprawdź rozszerzenie pliku
                    if any(file.endswith(ext) for ext in FILES_TO_BACKUP_EXTENSIONS):
                        arcname = os.path.relpath(file_path, SCRIPT_DIR)
                        zipf.write(file_path, arcname)
                        logger.debug(f"Dodano do archiwum: {arcname}")
        
        logger.info(f"Backup plików programu zakończony pomyślnie: {archive_path}")
        return True
    except Exception as e:
        logger.error(f"Błąd podczas tworzenia backupu plików programu: {e}", exc_info=True)
        return False

def backup_mysql_database():
    """Wykonuje zrzut bazy danych MySQL używając mysqldump."""
    if not create_backup_directory():
        return False

    # Załaduj konfigurację bazy danych
    try:
        config_handler.load_config(force_reload=True)
        db_config = config_handler.current_config.get("database")
        if not db_config or not all(db_config.get(k, {}).get("value") for k in ["host", "user", "password", "database"]):
            logger.error("Konfiguracja bazy danych w config.json jest niekompletna lub niepoprawna.")
            return False
    except Exception as e:
        logger.error(f"Błąd ładowania konfiguracji bazy danych: {e}", exc_info=True)
        return False

    db_host = db_config["host"]["value"]
    db_user = db_config["user"]["value"]
    db_password = db_config["password"]["value"]
    db_name = db_config["database"]["value"]
    db_port = db_config.get("port", {}).get("value", 3306) # Domyślny port MySQL

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"db_{db_name}_backup_{timestamp}.sql"
    backup_filepath = os.path.join(BACKUP_BASE_PATH, backup_filename)

    logger.info(f"Rozpoczynam backup bazy danych '{db_name}' do: {backup_filepath}")

    command = [
        MYSQLDUMP_PATH,
        f"--host={db_host}",
        f"--port={db_port}",
        f"--user={db_user}",
        f"--password={db_password}",
        "--single-transaction", # Dla tabel InnoDB, aby zapewnić spójność
        "--routines",           # Dołącz procedury składowane i funkcje
        "--triggers",           # Dołącz triggery
        "--events",             # Dołącz zdarzenia
        db_name
    ]

    try:
        with open(backup_filepath, 'wb') as f_out: # Otwórz w trybie binarnym dla outputu mysqldump
            process = subprocess.Popen(command, stdout=f_out, stderr=subprocess.PIPE, shell=sys.platform == "win32")
            stderr_output = process.communicate()[1] # Odczytaj stderr

            if process.returncode == 0:
                logger.info(f"Backup bazy danych '{db_name}' zakończony pomyślnie: {backup_filepath}")
                # Sprawdź, czy stderr nie zawiera ostrzeżeń (mysqldump czasami wysyła je na stderr)
                if stderr_output:
                    logger.warning(f"Komunikaty z mysqldump (stderr):\n{stderr_output.decode(errors='replace')}")
                return True
            else:
                error_message = f"Błąd podczas wykonywania mysqldump (kod: {process.returncode})."
                if stderr_output:
                    error_message += f"\nKomunikat błędu mysqldump:\n{stderr_output.decode(errors='replace')}"
                logger.error(error_message)
                # Usuń niekompletny plik backupu w razie błędu
                if os.path.exists(backup_filepath):
                    os.remove(backup_filepath)
                return False
                
    except FileNotFoundError:
        logger.error(f"Nie znaleziono programu mysqldump. Upewnij się, że jest w PATH lub podaj poprawną ścieżkę w MYSQLDUMP_PATH.")
        logger.error(f"Próbowano użyć: {MYSQLDUMP_PATH}")
        return False
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd podczas tworzenia backupu bazy danych: {e}", exc_info=True)
        if os.path.exists(backup_filepath): # Usuń plik, jeśli coś poszło nie tak
            try: os.remove(backup_filepath)
            except: pass
        return False

def main():
    logger.info(">>> Rozpoczynanie procesu backupu <<<")
    
    files_backup_ok = backup_program_files()
    db_backup_ok = backup_mysql_database()

    if files_backup_ok and db_backup_ok:
        logger.info(">>> Wszystkie operacje backupu zakończone pomyślnie! <<<")
    elif files_backup_ok:
        logger.warning(">>> Backup plików programu zakończony pomyślnie, ale wystąpił błąd podczas backupu bazy danych. <<<")
    elif db_backup_ok:
        logger.warning(">>> Backup bazy danych zakończony pomyślnie, ale wystąpił błąd podczas backupu plików programu. <<<")
    else:
        logger.error(">>> Wystąpiły błędy podczas obu operacji backupu (pliki i baza danych). <<<")

if __name__ == "__main__":
    # Ustawienie logowania do pliku dla tego skryptu
    log_file_handler = logging.FileHandler(os.path.join(SCRIPT_DIR, 'backup_manager.log'), mode='a', encoding='utf-8')
    log_file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)-8s] [%(name)-20s:%(lineno)4d] %(message)s'))
    logging.getLogger().addHandler(log_file_handler)
    
    main()