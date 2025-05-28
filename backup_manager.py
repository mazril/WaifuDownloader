# -*- coding: utf-8 -*-
import os
import sys
import shutil
import zipfile
import datetime
import subprocess
import logging
import re # Do parsowania daty z nazwy pliku

# Dodaj ścieżkę do katalogu nadrzędnego, aby importować moduły aplikacji
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config_handler 

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-8s] %(message)s')
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR_NAME = "_backups"
BACKUP_BASE_PATH = os.path.join(SCRIPT_DIR, BACKUP_DIR_NAME)

# --- Konfiguracja Ścieżek Narzędzi MySQL ---
# DOSTOSUJ TE ŚCIEŻKI, JEŚLI NARZĘDZIA NIE SĄ W SYSTEMOWEJ ZMIENNEJ PATH
MYSQLDUMP_PATH = r"C:\xampp\mysql\bin\mysqldump.exe" # Podaj pełną ścieżkę
MYSQL_CLIENT_PATH = r"C:\xampp\mysql\bin\mysql.exe"    # Podaj pełną ścieżkę

FILES_TO_BACKUP_EXTENSIONS = ['.py', '.php', '.json', '.crx', '.txt']
FILES_TO_IGNORE_ON_BACKUP = [ # Zmieniono nazwę dla jasności
    BACKUP_DIR_NAME,
    "__pycache__",
    ".git",
    ".vscode",
    "script.log", 
    "backup_manager.log", 
    "Modelki" # Folder Modelki jest ignorowany przy backupie plików programu
]
# Foldery i pliki, które NIE POWINNY być usuwane/nadpisywane podczas przywracania plików programu
# Obejmuje to sam skrypt backupu, jego log, katalog backupów oraz config.json (który zawiera dane DB)
FILES_TO_PRESERVE_ON_RESTORE = [
    os.path.basename(__file__), # Nazwa tego skryptu
    "backup_manager.log",
    BACKUP_DIR_NAME,
    config_handler.constants.CONFIG_FILENAME, # Używamy stałej z config_handler
    "script.log.bak", # Potencjalne backupy logów
    "script.log.1",
    "script.log.2",
    "script.log.3"
]


def ensure_backup_directory_exists():
    """Tworzy katalog na backupy, jeśli nie istnieje i zwraca jego ścieżkę."""
    if not os.path.exists(BACKUP_BASE_PATH):
        try:
            os.makedirs(BACKUP_BASE_PATH)
            logger.info(f"Utworzono katalog na backupy: {BACKUP_BASE_PATH}")
        except OSError as e:
            logger.error(f"Nie udało się utworzyć katalogu na backupy {BACKUP_BASE_PATH}: {e}")
            return None
    return BACKUP_BASE_PATH

def backup_program_files():
    backup_dir = ensure_backup_directory_exists()
    if not backup_dir: return False

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"program_files_backup_{timestamp}.zip"
    archive_path = os.path.join(backup_dir, archive_name)

    logger.info(f"Rozpoczynam backup plików programu do: {archive_path}")
    try:
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(SCRIPT_DIR):
                # Ignorowanie określonych folderów na poziomie głównym
                if os.path.abspath(root) == os.path.abspath(SCRIPT_DIR):
                    dirs[:] = [d for d in dirs if d not in FILES_TO_IGNORE_ON_BACKUP and not d.startswith('.')]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_file_path_for_check = os.path.relpath(file_path, SCRIPT_DIR)
                    
                    should_ignore_file = False
                    # Sprawdź, czy plik lub jego ścieżka nadrzędna zaczyna się od ignorowanego elementu
                    for ignored_item in FILES_TO_IGNORE_ON_BACKUP:
                        if relative_file_path_for_check.startswith(ignored_item + os.sep) or \
                           relative_file_path_for_check == ignored_item:
                            should_ignore_file = True
                            break
                    
                    if should_ignore_file or file_path == archive_path:
                        continue

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
    backup_dir = ensure_backup_directory_exists()
    if not backup_dir: return False

    try:
        config_handler.load_config(force_reload=True)
        db_config = config_handler.current_config.get("database")
        if not db_config or not all(db_config.get(k, {}).get("value") for k in ["host", "user", "database"]):
            logger.error("Konfiguracja bazy danych w config.json jest niekompletna.")
            return False
    except Exception as e:
        logger.error(f"Błąd ładowania konfiguracji bazy danych: {e}", exc_info=True)
        return False

    db_host = db_config["host"]["value"]
    db_user = db_config["user"]["value"]
    db_password = db_config.get("password", {}).get("value", "") 
    db_name = db_config["database"]["value"]
    db_port = str(db_config.get("port", {}).get("value", 3306))

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"db_{db_name}_backup_{timestamp}.sql"
    backup_filepath = os.path.join(backup_dir, backup_filename)

    logger.info(f"Rozpoczynam backup bazy danych '{db_name}' do: {backup_filepath}")
    command = [MYSQLDUMP_PATH, f"--host={db_host}", f"--port={db_port}", f"--user={db_user}"]
    if db_password: command.append(f"--password={db_password}")
    command.extend(["--single-transaction", "--routines", "--triggers", "--events", db_name])

    process = None
    f_out = None
    try:
        f_out = open(backup_filepath, 'w', encoding='utf-8')
        executable_path = MYSQLDUMP_PATH
        if ' ' in executable_path and not (executable_path.startswith('"') and executable_path.endswith('"')):
            executable_path = f'"{executable_path}"'
        
        final_command_list = command.copy()
        final_command_list[0] = executable_path

        logger.debug(f"Wykonywanie polecenia: {' '.join(final_command_list)}")
        process = subprocess.Popen(final_command_list, stdout=f_out, stderr=subprocess.PIPE, shell=False)
        stderr_output_bytes, stdout_output_bytes = process.communicate()
        stderr_output = stderr_output_bytes.decode(errors='replace') if stderr_output_bytes else ""

        if process.returncode == 0:
            logger.info(f"Backup bazy danych '{db_name}' zakończony pomyślnie: {backup_filepath}")
            if stderr_output: logger.warning(f"Komunikaty z mysqldump (stderr):\n{stderr_output}")
            return True
        else:
            error_message = f"Błąd podczas wykonywania mysqldump (kod: {process.returncode})."
            if stderr_output: error_message += f"\nKomunikat błędu mysqldump:\n{stderr_output}"
            logger.error(error_message)
            return False
    except FileNotFoundError:
        logger.error(f"Nie znaleziono programu mysqldump. Ścieżka: '{MYSQLDUMP_PATH}'. Upewnij się, że jest poprawna i program istnieje.")
        return False
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd podczas tworzenia backupu bazy danych: {e}", exc_info=True)
        return False
    finally:
        if f_out: f_out.close()
        if process and process.returncode != 0 and os.path.exists(backup_filepath):
            try:
                logger.info(f"Próba usunięcia niekompletnego pliku backupu: {backup_filepath}")
                os.remove(backup_filepath)
            except Exception as e_rem:
                logger.error(f"Nie udało się usunąć niekompletnego pliku backupu {backup_filepath}: {e_rem}")

def list_backups():
    """Listuje dostępne backupy plików i bazy danych."""
    backup_dir = ensure_backup_directory_exists()
    if not backup_dir: return [], []

    program_backups = []
    db_backups = []
    
    for filename in os.listdir(backup_dir):
        if filename.startswith("program_files_backup_") and filename.endswith(".zip"):
            try:
                # Regex do wyciągnięcia daty i godziny
                match = re.search(r"program_files_backup_(\d{8}_\d{6})\.zip", filename)
                if match:
                    dt_str = match.group(1)
                    dt_obj = datetime.datetime.strptime(dt_str, "%Y%m%d_%H%M%S")
                    program_backups.append({"filename": filename, "datetime": dt_obj, "type": "files"})
            except ValueError:
                logger.warning(f"Nie udało się sparsować daty z nazwy pliku backupu plików: {filename}")
        elif filename.startswith("db_") and filename.endswith(".sql"):
            try:
                match = re.search(r"db_.+?_backup_(\d{8}_\d{6})\.sql", filename)
                if match:
                    dt_str = match.group(1)
                    dt_obj = datetime.datetime.strptime(dt_str, "%Y%m%d_%H%M%S")
                    db_backups.append({"filename": filename, "datetime": dt_obj, "type": "db"})
            except ValueError:
                logger.warning(f"Nie udało się sparsować daty z nazwy pliku backupu bazy: {filename}")
                
    program_backups.sort(key=lambda x: x["datetime"], reverse=True)
    db_backups.sort(key=lambda x: x["datetime"], reverse=True)
    return program_backups, db_backups

def restore_program_files(zip_backup_path):
    """Przywraca pliki programu z wybranego archiwum ZIP."""
    if not os.path.exists(zip_backup_path):
        logger.error(f"Plik backupu plików programu nie istnieje: {zip_backup_path}")
        return False

    logger.info(f"Rozpoczynam przywracanie plików programu z: {zip_backup_path}")
    logger.warning("UWAGA: Istniejące pliki (z wyjątkiem chronionych) w katalogu projektu zostaną nadpisane!")

    try:
        # Najpierw usuń stare pliki (z wyjątkiem chronionych)
        for item in os.listdir(SCRIPT_DIR):
            item_path = os.path.join(SCRIPT_DIR, item)
            if item not in FILES_TO_PRESERVE_ON_RESTORE:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                    logger.debug(f"Usunięto plik: {item_path}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    logger.debug(f"Usunięto katalog: {item_path}")
        
        # Rozpakuj archiwum
        with zipfile.ZipFile(zip_backup_path, 'r') as zipf:
            zipf.extractall(SCRIPT_DIR)
        logger.info(f"Pomyślnie przywrócono pliki programu z {zip_backup_path} do {SCRIPT_DIR}")
        return True
    except Exception as e:
        logger.error(f"Błąd podczas przywracania plików programu: {e}", exc_info=True)
        return False

def restore_mysql_database(sql_backup_path):
    """Przywraca bazę danych MySQL z pliku .sql."""
    if not os.path.exists(sql_backup_path):
        logger.error(f"Plik backupu bazy danych nie istnieje: {sql_backup_path}")
        return False

    try:
        config_handler.load_config(force_reload=True) # Załaduj najnowszą konfigurację
        db_config = config_handler.current_config.get("database")
        if not db_config or not all(db_config.get(k, {}).get("value") for k in ["host", "user", "database"]):
            logger.error("Konfiguracja bazy danych w config.json jest niekompletna.")
            return False
    except Exception as e:
        logger.error(f"Błąd ładowania konfiguracji bazy danych: {e}", exc_info=True)
        return False

    db_host = db_config["host"]["value"]
    db_user = db_config["user"]["value"]
    db_password = db_config.get("password", {}).get("value", "")
    db_name = db_config["database"]["value"]
    db_port = str(db_config.get("port", {}).get("value", 3306))

    logger.info(f"Rozpoczynam przywracanie bazy danych '{db_name}' z pliku: {sql_backup_path}")
    logger.warning(f"UWAGA: Istniejąca baza danych '{db_name}' zostanie NAJPIERW USUNIĘTA, a następnie utworzona na nowo i wypełniona danymi z backupu!")
    
    if input("Czy na pewno chcesz kontynuować? (tak/nie): ").lower() != 'tak':
        logger.info("Przywracanie bazy danych anulowane przez użytkownika.")
        return False

    # 1. Usuń starą bazę danych
    drop_command = [MYSQL_CLIENT_PATH, f"--host={db_host}", f"--port={db_port}", f"--user={db_user}"]
    if db_password: drop_command.append(f"--password={db_password}")
    drop_command.append("-e", f"DROP DATABASE IF EXISTS {db_name}")
    
    executable_client_path = MYSQL_CLIENT_PATH
    if ' ' in executable_client_path and not (executable_client_path.startswith('"') and executable_client_path.endswith('"')):
            executable_client_path = f'"{executable_client_path}"'
    drop_command[0] = executable_client_path


    logger.info(f"Usuwanie istniejącej bazy danych '{db_name}'...")
    try:
        process_drop = subprocess.Popen(drop_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        stdout_drop, stderr_drop_bytes = process_drop.communicate()
        stderr_drop = stderr_drop_bytes.decode(errors='replace') if stderr_drop_bytes else ""
        if process_drop.returncode != 0:
            logger.error(f"Błąd podczas usuwania bazy danych '{db_name}' (kod: {process_drop.returncode}). Komunikat: {stderr_drop}")
            return False
        logger.info(f"Baza danych '{db_name}' usunięta (lub nie istniała).")
    except FileNotFoundError:
        logger.error(f"Nie znaleziono programu mysql client. Ścieżka: '{MYSQL_CLIENT_PATH}'. Upewnij się, że jest poprawna.")
        return False
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd podczas usuwania bazy danych: {e}", exc_info=True)
        return False

    # 2. Utwórz nową, pustą bazę danych
    create_command = [MYSQL_CLIENT_PATH, f"--host={db_host}", f"--port={db_port}", f"--user={db_user}"]
    if db_password: create_command.append(f"--password={db_password}")
    create_command.append("-e", f"CREATE DATABASE {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    create_command[0] = executable_client_path

    logger.info(f"Tworzenie nowej bazy danych '{db_name}'...")
    try:
        process_create = subprocess.Popen(create_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
        stdout_create, stderr_create_bytes = process_create.communicate()
        stderr_create = stderr_create_bytes.decode(errors='replace') if stderr_create_bytes else ""
        if process_create.returncode != 0:
            logger.error(f"Błąd podczas tworzenia bazy danych '{db_name}' (kod: {process_create.returncode}). Komunikat: {stderr_create}")
            return False
        logger.info(f"Baza danych '{db_name}' utworzona pomyślnie.")
    except Exception as e: # FileNotFoundError jest już obsłużone wyżej
        logger.error(f"Nieoczekiwany błąd podczas tworzenia bazy danych: {e}", exc_info=True)
        return False

    # 3. Zaimportuj dane z pliku .sql
    import_command = [MYSQL_CLIENT_PATH, f"--host={db_host}", f"--port={db_port}", f"--user={db_user}"]
    if db_password: import_command.append(f"--password={db_password}")
    import_command.append(db_name) 
    import_command[0] = executable_client_path

    logger.info(f"Importowanie danych do bazy '{db_name}' z pliku {sql_backup_path}...")
    try:
        with open(sql_backup_path, 'r', encoding='utf-8') as f_in: # Pliki SQL to zwykle tekst
            process_import = subprocess.Popen(import_command, stdin=f_in, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
            stdout_import, stderr_import_bytes = process_import.communicate()
            stderr_import = stderr_import_bytes.decode(errors='replace') if stderr_import_bytes else ""

            if process_import.returncode == 0:
                logger.info(f"Pomyślnie przywrócono bazę danych '{db_name}' z pliku {sql_backup_path}.")
                if stderr_import:
                    logger.warning(f"Komunikaty z mysql client podczas importu (stderr):\n{stderr_import}")
                return True
            else:
                error_message = f"Błąd podczas importowania bazy danych '{db_name}' (kod: {process_import.returncode})."
                if stderr_import:
                    error_message += f"\nKomunikat błędu mysql client:\n{stderr_import}"
                logger.error(error_message)
                return False
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd podczas importowania bazy danych: {e}", exc_info=True)
        return False


def display_backup_list(backups, backup_type_name):
    """Wyświetla ponumerowaną listę backupów."""
    if not backups:
        logger.info(f"Nie znaleziono żadnych backupów typu: {backup_type_name}.")
        return None
    
    print(f"\nDostępne backupy dla '{backup_type_name}':")
    for i, backup_info in enumerate(backups):
        print(f"  {i+1}. {backup_info['filename']} (Data: {backup_info['datetime'].strftime('%Y-%m-%d %H:%M:%S')})")
    
    while True:
        try:
            choice = input(f"Wybierz numer backupu '{backup_type_name}' do przywrócenia (lub 0 aby anulować): ")
            choice_int = int(choice)
            if 0 <= choice_int <= len(backups):
                if choice_int == 0: return None
                return backups[choice_int - 1] # Zwróć wybrany słownik backup_info
            else:
                print("Nieprawidłowy wybór. Spróbuj ponownie.")
        except ValueError:
            print("Nieprawidłowe wejście. Wprowadź liczbę.")

def main_menu():
    """Wyświetla główne menu i obsługuje wybór użytkownika."""
    while True:
        print("\n--- Zarządzanie Backupem ---")
        print("1. Wykonaj pełny backup (pliki programu i baza danych)")
        print("2. Przywróć z backupu")
        print("3. Wyjdź")
        choice = input("Wybierz opcję: ")

        if choice == '1':
            logger.info(">>> Rozpoczynanie procesu backupu <<<")
            files_ok = backup_program_files()
            db_ok = backup_mysql_database()
            if files_ok and db_ok: logger.info(">>> Wszystkie operacje backupu zakończone pomyślnie! <<<")
            else: logger.error(">>> Wystąpiły błędy podczas procesu backupu. Sprawdź logi. <<<")
        elif choice == '2':
            handle_restore()
        elif choice == '3':
            logger.info("Zamykanie menedżera backupu.")
            break
        else:
            print("Nieprawidłowy wybór, spróbuj ponownie.")

def handle_restore():
    """Obsługuje proces przywracania."""
    logger.info(">>> Rozpoczynanie procesu przywracania z backupu <<<")
    program_backups, db_backups = list_backups()

    if not program_backups and not db_backups:
        logger.info("Brak dostępnych backupów do przywrócenia.")
        return

    # Przywracanie plików programu
    selected_program_backup = None
    if program_backups:
        selected_program_backup_info = display_backup_list(program_backups, "Pliki Programu")
        if selected_program_backup_info:
            selected_program_backup_path = os.path.join(BACKUP_BASE_PATH, selected_program_backup_info["filename"])
            if input(f"Czy na pewno chcesz przywrócić pliki programu z '{selected_program_backup_info['filename']}'? (tak/nie): ").lower() == 'tak':
                restore_program_files(selected_program_backup_path)
            else:
                logger.info("Przywracanie plików programu anulowane.")
        else:
            logger.info("Nie wybrano backupu plików programu do przywrócenia.")
    else:
        logger.info("Brak backupów plików programu do przywrócenia.")

    # Przywracanie bazy danych
    selected_db_backup = None
    if db_backups:
        selected_db_backup_info = display_backup_list(db_backups, "Baza Danych")
        if selected_db_backup_info:
            selected_db_backup_path = os.path.join(BACKUP_BASE_PATH, selected_db_backup_info["filename"])
            # Potwierdzenie jest już w funkcji restore_mysql_database
            restore_mysql_database(selected_db_backup_path) 
        else:
            logger.info("Nie wybrano backupu bazy danych do przywrócenia.")
    else:
        logger.info("Brak backupów bazy danych do przywrócenia.")
    
    logger.info(">>> Proces przywracania zakończony (lub anulowany). Sprawdź logi. <<<")


if __name__ == "__main__":
    log_file_handler = logging.FileHandler(os.path.join(SCRIPT_DIR, 'backup_manager.log'), mode='a', encoding='utf-8')
    log_file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)-8s] [%(name)-20s:%(lineno)4d] %(message)s'))
    logging.getLogger().addHandler(log_file_handler)
    
    main_menu()