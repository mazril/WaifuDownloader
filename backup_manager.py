# -*- coding: utf-8 -*-
import os
import sys
import shutil
import zipfile
import datetime
import subprocess
import logging
import re 

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config_handler 

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-8s] %(message)s')
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR_NAME = "_backups"
BACKUP_BASE_PATH = os.path.join(SCRIPT_DIR, BACKUP_DIR_NAME)

MYSQLDUMP_PATH = r"C:\xampp\mysql\bin\mysqldump.exe" 
MYSQL_CLIENT_PATH = r"C:\xampp\mysql\bin\mysql.exe"    

FILES_TO_BACKUP_EXTENSIONS = ['.py', '.php', '.json', '.crx', '.txt']
FILES_TO_IGNORE_ON_BACKUP = [ 
    BACKUP_DIR_NAME,
    "__pycache__",
    ".git", # Ignoruj .git przy tworzeniu backupu
    ".vscode",
    "script.log", 
    "backup_manager.log", 
    "Modelki" 
]
FILES_TO_PRESERVE_ON_RESTORE = [
    os.path.basename(__file__), 
    "backup_manager.log",
    BACKUP_DIR_NAME,
    "config.json", 
    ".git", # Nie usuwaj .git przy przywracaniu
    "script.log.bak", 
    "script.log.1",
    "script.log.2",
    "script.log.3"
]


def ensure_backup_directory_exists():
    if not os.path.exists(BACKUP_BASE_PATH):
        try:
            os.makedirs(BACKUP_BASE_PATH)
            logger.info(f"Utworzono katalog na backupy: {BACKUP_BASE_PATH}")
        except OSError as e:
            logger.error(f"Nie udało się utworzyć katalogu na backupy {BACKUP_BASE_PATH}: {e}")
            return None
    return BACKUP_BASE_PATH

def generate_timestamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def backup_program_files(timestamp):
    backup_dir = ensure_backup_directory_exists()
    if not backup_dir: return False

    archive_name = f"program_files_backup_{timestamp}.zip"
    archive_path = os.path.join(backup_dir, archive_name)

    logger.info(f"Rozpoczynam backup plików programu do: {archive_path}")
    try:
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(SCRIPT_DIR):
                # Ignorowanie folderów na podstawie ich nazw (dla folderów w SCRIPT_DIR)
                if os.path.abspath(root) == os.path.abspath(SCRIPT_DIR):
                    dirs[:] = [d for d in dirs if d not in FILES_TO_IGNORE_ON_BACKUP and not d.startswith('.')]
                
                # Ignorowanie folderów na podstawie pełnej ścieżki (dla podfolderów)
                # Ta linia jest kluczowa, aby shutil.rmtree nie próbował usuwać .git/objects/...
                dirs[:] = [d for d in dirs if os.path.join(root, d) not in [os.path.join(SCRIPT_DIR, ig_item) for ig_item in FILES_TO_IGNORE_ON_BACKUP if os.path.isdir(os.path.join(SCRIPT_DIR, ig_item))]]


                for file in files:
                    file_path = os.path.join(root, file)
                    relative_file_path_for_check = os.path.relpath(file_path, SCRIPT_DIR)
                    
                    should_ignore_file = False
                    # Sprawdź, czy plik lub jego ścieżka nadrzędna zaczyna się od ignorowanego elementu
                    # lub czy jest to samo archiwum backupu
                    if file_path == archive_path:
                        should_ignore_file = True
                    else:
                        for ignored_item in FILES_TO_IGNORE_ON_BACKUP:
                            # Sprawdź, czy ścieżka względna zaczyna się od ignorowanego folderu
                            if relative_file_path_for_check.startswith(ignored_item + os.sep) or \
                               relative_file_path_for_check == ignored_item:
                                should_ignore_file = True
                                break
                    
                    if should_ignore_file:
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

def backup_mysql_database(timestamp):
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

def list_backup_sets():
    backup_dir = ensure_backup_directory_exists()
    if not backup_dir: return []

    backups = {} 
    
    for filename in os.listdir(backup_dir):
        if filename.startswith("program_files_backup_") and filename.endswith(".zip"):
            match = re.search(r"program_files_backup_(\d{8}_\d{6})\.zip", filename)
            if match:
                ts = match.group(1)
                if ts not in backups: backups[ts] = {}
                backups[ts]["files"] = filename
                try: backups[ts]["datetime"] = datetime.datetime.strptime(ts, "%Y%m%d_%H%M%S")
                except ValueError: pass 
        elif filename.startswith("db_") and filename.endswith(".sql"):
            match = re.search(r"db_.+?_backup_(\d{8}_\d{6})\.sql", filename)
            if match:
                ts = match.group(1)
                if ts not in backups: backups[ts] = {}
                backups[ts]["db"] = filename
                try: backups[ts]["datetime"] = datetime.datetime.strptime(ts, "%Y%m%d_%H%M%S")
                except ValueError: pass

    complete_sets = []
    for ts, data in backups.items():
        if "files" in data and "db" in data and "datetime" in data:
            complete_sets.append({
                "timestamp_str": ts,
                "files_backup_name": data["files"],
                "db_backup_name": data["db"],
                "datetime_obj": data["datetime"]
            })
            
    complete_sets.sort(key=lambda x: x["datetime_obj"], reverse=True)
    return complete_sets


def restore_program_files(zip_backup_path):
    if not os.path.exists(zip_backup_path):
        logger.error(f"Plik backupu plików programu nie istnieje: {zip_backup_path}")
        return False

    logger.info(f"Rozpoczynam przywracanie plików programu z: {zip_backup_path}")
    
    preserved_full_paths = [os.path.join(SCRIPT_DIR, p) for p in FILES_TO_PRESERVE_ON_RESTORE]

    try:
        for item_name in os.listdir(SCRIPT_DIR):
            item_full_path = os.path.join(SCRIPT_DIR, item_name)
            
            # Sprawdź, czy pełna ścieżka jest na liście do zachowania
            if item_full_path in preserved_full_paths or \
               (os.path.isdir(item_full_path) and item_name in FILES_TO_PRESERVE_ON_RESTORE): # Dodatkowe sprawdzenie dla folderów
                logger.debug(f"Pomijam usuwanie chronionego elementu: {item_full_path}")
                continue

            try:
                if os.path.isfile(item_full_path) or os.path.islink(item_full_path):
                    os.unlink(item_full_path)
                    logger.debug(f"Usunięto plik: {item_full_path}")
                elif os.path.isdir(item_full_path):
                    shutil.rmtree(item_full_path) # Ten może nadal rzucić błąd dla .git
                    logger.debug(f"Usunięto katalog: {item_full_path}")
            except PermissionError as pe:
                logger.warning(f"Odmowa dostępu podczas próby usunięcia '{item_full_path}': {pe}. Kontynuuję z pozostałymi.")
            except Exception as e_del:
                logger.error(f"Błąd podczas usuwania '{item_full_path}': {e_del}. Kontynuuję z pozostałymi.")
        
        with zipfile.ZipFile(zip_backup_path, 'r') as zipf:
            for member in zipf.namelist():
                target_path = os.path.join(SCRIPT_DIR, member)
                # Sprawdź, czy ścieżka docelowa nie jest jednym z chronionych elementów
                # To jest drugie zabezpieczenie, gdyby usuwanie zawiodło a archiwum zawierało chroniony plik
                is_preserved = False
                for preserved_item_name in FILES_TO_PRESERVE_ON_RESTORE:
                    preserved_full_item_path = os.path.join(SCRIPT_DIR, preserved_item_name)
                    if os.path.abspath(target_path) == os.path.abspath(preserved_full_item_path) or \
                       (os.path.isdir(preserved_full_item_path) and target_path.startswith(preserved_full_item_path + os.sep)):
                        is_preserved = True
                        logger.debug(f"Pomijam nadpisywanie chronionego elementu '{member}' z archiwum.")
                        break
                if not is_preserved:
                    zipf.extract(member, SCRIPT_DIR)
                    logger.debug(f"Przywrócono plik z archiwum: {member}")

        logger.info(f"Pomyślnie przywrócono pliki programu z {zip_backup_path} do {SCRIPT_DIR}")
        return True
    except Exception as e:
        logger.error(f"Błąd podczas przywracania plików programu: {e}", exc_info=True)
        return False

def restore_mysql_database(sql_backup_path):
    if not os.path.exists(sql_backup_path):
        logger.error(f"Plik backupu bazy danych nie istnieje: {sql_backup_path}")
        return False

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

    logger.info(f"Przywracanie bazy danych '{db_name}' z pliku: {sql_backup_path}")
    
    drop_command = [MYSQL_CLIENT_PATH, f"--host={db_host}", f"--port={db_port}", f"--user={db_user}"]
    if db_password: drop_command.append(f"--password={db_password}")
    drop_command.extend(["-e", f"DROP DATABASE IF EXISTS {db_name}"]) 
    
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
            if "Unknown database" not in stderr_drop and "Can't drop database" not in stderr_drop :
                 logger.error(f"Błąd podczas usuwania bazy danych '{db_name}' (kod: {process_drop.returncode}). Komunikat: {stderr_drop}")
                 return False
            else:
                 logger.info(f"Baza '{db_name}' nie istniała lub nie można było jej usunąć. Kontynuuję.")
        else:
            logger.info(f"Baza danych '{db_name}' usunięta (jeśli istniała).")
    except FileNotFoundError:
        logger.error(f"Nie znaleziono programu mysql client. Ścieżka: '{MYSQL_CLIENT_PATH}'. Upewnij się, że jest poprawna.")
        return False
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd podczas usuwania bazy danych: {e}", exc_info=True)
        return False

    create_command = [MYSQL_CLIENT_PATH, f"--host={db_host}", f"--port={db_port}", f"--user={db_user}"]
    if db_password: create_command.append(f"--password={db_password}")
    create_command.extend(["-e", f"CREATE DATABASE {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"])
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
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd podczas tworzenia bazy danych: {e}", exc_info=True)
        return False

    import_command = [MYSQL_CLIENT_PATH, f"--host={db_host}", f"--port={db_port}", f"--user={db_user}"]
    if db_password: import_command.append(f"--password={db_password}")
    import_command.append(db_name) 
    import_command[0] = executable_client_path

    logger.info(f"Importowanie danych do bazy '{db_name}' z pliku {sql_backup_path}...")
    try:
        with open(sql_backup_path, 'r', encoding='utf-8') as f_in: 
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


def display_and_select_backup_set(backup_sets):
    if not backup_sets:
        logger.info("Nie znaleziono żadnych kompletnych zestawów backupów (pliki + baza danych).")
        return None
    
    print("\nDostępne kompletne zestawy backupów (posortowane od najnowszych):")
    for i, backup_set in enumerate(backup_sets):
        print(f"  {i+1}. Data: {backup_set['datetime_obj'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"     Pliki: {backup_set['files_backup_name']}")
        print(f"     Baza:  {backup_set['db_backup_name']}")
    
    while True:
        try:
            choice = input("Wybierz numer zestawu backupu do przywrócenia (lub 0 aby anulować): ")
            choice_int = int(choice)
            if 0 <= choice_int <= len(backup_sets):
                if choice_int == 0: return None
                return backup_sets[choice_int - 1]
            else:
                print("Nieprawidłowy wybór. Spróbuj ponownie.")
        except ValueError:
            print("Nieprawidłowe wejście. Wprowadź liczbę.")


def handle_restore_set():
    logger.info(">>> Rozpoczynanie procesu przywracania z backupu <<<")
    backup_sets = list_backup_sets()

    if not backup_sets:
        return

    selected_set = display_and_select_backup_set(backup_sets)
    if not selected_set:
        logger.info("Nie wybrano zestawu backupu do przywrócenia.")
        return

    logger.warning("-" * 50)
    logger.warning("UWAGA: Wybrano przywracanie następującego zestawu backupu:")
    logger.warning(f"  Data: {selected_set['datetime_obj'].strftime('%Y-%m-%d %H:%M:%S')}")
    logger.warning(f"  Pliki programu z: {selected_set['files_backup_name']}")
    logger.warning(f"  Baza danych z:    {selected_set['db_backup_name']}")
    logger.warning("Ta operacja NADPISZE bieżące pliki programu (z wyjątkiem chronionych)")
    logger.warning("oraz CAŁKOWICIE USUNIE i ZASTĄPI bieżącą bazę danych.")
    logger.warning("-" * 50)
    
    if input("Czy na pewno chcesz kontynuować z przywracaniem tego zestawu? (tak/nie): ").lower() != 'tak':
        logger.info("Przywracanie zestawu backupu anulowane przez użytkownika.")
        return

    files_backup_path = os.path.join(BACKUP_BASE_PATH, selected_set["files_backup_name"])
    db_backup_path = os.path.join(BACKUP_BASE_PATH, selected_set["db_backup_name"])

    logger.info("--- Rozpoczynanie przywracania plików programu ---")
    files_restored_ok = restore_program_files(files_backup_path)
    if files_restored_ok:
        logger.info("--- Przywracanie plików programu zakończone pomyślnie ---")
    else:
        logger.error("!!! Błąd podczas przywracania plików programu. Sprawdź logi. Rozważ ręczne przywrócenie. !!!")
        if input("Wystąpił błąd przywracania plików. Czy mimo to kontynuować z przywracaniem bazy danych? (tak/nie): ").lower() != 'tak':
            logger.info("Przywracanie bazy danych anulowane po błędzie przywracania plików.")
            return

    logger.info("--- Rozpoczynanie przywracania bazy danych ---")
    # Potwierdzenie przywrócenia bazy jest teraz w tej funkcji, ale już było jedno ogólne.
    # Można by usunąć wewnętrzne potwierdzenie z restore_mysql_database, jeśli to jest uciążliwe.
    db_restored_ok = restore_mysql_database(db_backup_path) 
    if db_restored_ok:
        logger.info("--- Przywracanie bazy danych zakończone pomyślnie ---")
    else:
        logger.error("!!! Błąd podczas przywracania bazy danych. Sprawdź logi. Baza może być w niekonsystentnym stanie! !!!")

    if files_restored_ok and db_restored_ok:
        logger.info(">>> Pełne przywracanie z zestawu backupu zakończone pomyślnie. <<<")
    else:
        logger.warning(">>> Proces przywracania zakończony z błędami. Sprawdź dokładnie logi. <<<")


def main_menu():
    while True:
        print("\n--- Menedżer Backupów ---")
        print("1. Wykonaj pełny backup (pliki programu i baza danych)")
        print("2. Przywróć z kompletnego zestawu backupu")
        print("3. Wyjdź")
        choice = input("Wybierz opcję: ")

        if choice == '1':
            logger.info(">>> Rozpoczynanie procesu tworzenia nowego backupu <<<")
            current_timestamp = generate_timestamp() 
            files_ok = backup_program_files(current_timestamp)
            db_ok = False 
            if files_ok: 
                db_ok = backup_mysql_database(current_timestamp)
            
            if files_ok and db_ok: 
                logger.info(">>> Wszystkie operacje tworzenia backupu zakończone pomyślnie! <<<")
            else: 
                logger.error(">>> Wystąpiły błędy podczas tworzenia backupu. Sprawdź logi. <<<")
        elif choice == '2':
            handle_restore_set()
        elif choice == '3':
            logger.info("Zamykanie menedżera backupu.")
            break
        else:
            print("Nieprawidłowy wybór, spróbuj ponownie.")

if __name__ == "__main__":
    log_file_handler = logging.FileHandler(os.path.join(SCRIPT_DIR, 'backup_manager.log'), mode='a', encoding='utf-8')
    log_file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)-8s] [%(name)-20s:%(lineno)4d] %(message)s'))
    logging.getLogger().addHandler(log_file_handler)
    
    # Dynamiczne pobieranie nazwy pliku konfiguracyjnego
    config_file_name_to_preserve = "config.json" # Domyślna wartość
    try:
        # Sprawdź, czy config_handler i jego stałe są dostępne
        # To jest trochę nadmiarowe, bo config_handler jest importowany na górze
        # ale zostawiam dla bezpieczeństwa, jeśli struktura projektu by się zmieniła
        if 'config_handler' in sys.modules and \
           hasattr(config_handler, 'constants') and \
           hasattr(config_handler.constants, 'CONFIG_FILENAME'):
            config_file_name_to_preserve = config_handler.constants.CONFIG_FILENAME
    except Exception: # Ogólny wyjątek, jeśli coś pójdzie nie tak z dostępem do stałej
        logger.warning("Nie udało się dynamicznie pobrać nazwy pliku config z config_handler.constants. Używam domyślnej 'config.json' do zachowania.")

    # Upewnij się, że poprawna nazwa pliku config jest na liście do zachowania
    if config_file_name_to_preserve not in FILES_TO_PRESERVE_ON_RESTORE:
        # Usuń potencjalnie starą/domyślną wartość 'config.json', jeśli jest inna niż dynamicznie pobrana
        if "config.json" in FILES_TO_PRESERVE_ON_RESTORE and "config.json" != config_file_name_to_preserve:
            FILES_TO_PRESERVE_ON_RESTORE.remove("config.json")
        FILES_TO_PRESERVE_ON_RESTORE.append(config_file_name_to_preserve)
    # Usuń duplikaty, jeśli by powstały
    FILES_TO_PRESERVE_ON_RESTORE = list(set(FILES_TO_PRESERVE_ON_RESTORE))

    logger.debug(f"Pliki/foldery chronione podczas przywracania: {FILES_TO_PRESERVE_ON_RESTORE}")
    main_menu()