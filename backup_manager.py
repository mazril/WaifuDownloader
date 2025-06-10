# -*- coding: utf-8 -*-
import os
import sys
import shutil
import zipfile
import datetime
import subprocess
import logging
import re
import fnmatch

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config_handler
# Zakładamy, że constants.py może już nie istnieć lub być w trakcie zmiany,
# więc wartości takie jak BASE_DATA_DIR_NAME będą brane z config_handler lub zdefiniowane lokalnie.

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-8s] %(message)s')
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR_NAME = "_backups"
BACKUP_BASE_PATH = os.path.join(SCRIPT_DIR, BACKUP_DIR_NAME)
DB_STRUCTURE_FILE_NAME = "struktura_bazy_danych.txt"

# --- Konfiguracja Ścieżek Narzędzi MySQL ---
# ZMIANA: Zaktualizowano ścieżki, aby wskazywały na instalację WampServer zamiast XAMPP.
# Opis: Poprzednie ścieżki prowadziły do narzędzi z XAMPP, co powodowało błąd uwierzytelniania z nową bazą WampServer.
#       Teraz musisz podać poprawną ścieżkę do katalogu 'bin' Twojej wersji MySQL w WampServer.
#       Przykładowa ścieżka: C:\wamp64\bin\mysql\mysql8.0.30\bin\
# Wpływ: Ta zmiana jest kluczowa dla poprawnego działania funkcji `backup_mysql_database` i `restore_mysql_database`.
MYSQLDUMP_PATH = r"C:\wamp64\bin\mysql\mysql9.1.0\bin\mysqldump.exe"
MYSQL_CLIENT_PATH = r"C:\wamp64\bin\mysql\mysql9.1.0\bin\mysql.exe"


FILES_TO_BACKUP_EXTENSIONS = ['.py', '.php', '.json', '.crx', '.txt', '.css']

# Użyjemy BASE_DATA_DIR_NAME z config_handler.constants, jeśli dostępne, inaczej domyślne "Modelki"
BASE_DATA_DIR_NAME_CONST = "Modelki" # Domyślna nazwa
try:
    if hasattr(config_handler, 'constants') and hasattr(config_handler.constants, 'BASE_DATA_DIR_NAME'):
        BASE_DATA_DIR_NAME_CONST = config_handler.constants.BASE_DATA_DIR_NAME
except AttributeError:
    logger.warning("Nie można załadować BASE_DATA_DIR_NAME z config_handler.constants, używam domyślnej 'Modelki'.")


FILES_TO_IGNORE_ON_BACKUP = [
    BACKUP_DIR_NAME,
    "__pycache__",
    ".git",
    ".vscode",
    "script.txt",
    "backup_manager.log",
    BASE_DATA_DIR_NAME_CONST, # Folder z pobranymi plikami jest ignorowany przy backupie plików programu
    DB_STRUCTURE_FILE_NAME, # Plik ze strukturą bazy nie jest częścią backupu plików programu
    "backup_description_*.txt" # Wzorzec dla plików opisu backupu
]
FILES_TO_PRESERVE_ON_RESTORE = [
    os.path.basename(__file__),
    "backup_manager.log",
    BACKUP_DIR_NAME,
    "config.json", # Nazwa pliku konfiguracyjnego
    BASE_DATA_DIR_NAME_CONST, # ZAWSZE ZACHOWUJ KATALOG Z POBRANYMI PLIKAMI
    ".git",
    ".gitignore",
    "script.txt.bak",
    "script.txt.1",
    "script.txt.2",
    "script.txt.3"
    # Pliki .bat są chronione bezpośrednio w logice funkcji restore_program_files
]


def ensure_backup_directory_exists():
    """
    Zapewnia istnienie katalogu na backupy.

    Opis:
    Sprawdza, czy katalog zdefiniowany w BACKUP_BASE_PATH istnieje.
    Jeśli nie, próbuje go utworzyć.

    Wpływ na inne funkcje:
    - Wywoływana przez funkcje tworzące backupy (backup_program_files, backup_mysql_database)
      oraz przy zapisie opisu backupu w main_menu, aby upewnić się, że docelowy
      katalog istnieje.
    """
    if not os.path.exists(BACKUP_BASE_PATH):
        try:
            os.makedirs(BACKUP_BASE_PATH)
            logger.info(f"Utworzono katalog na backupy: {BACKUP_BASE_PATH}")
        except OSError as e:
            logger.error(f"Nie udało się utworzyć katalogu na backupy {BACKUP_BASE_PATH}: {e}")
            return None
    return BACKUP_BASE_PATH

def generate_timestamp():
    """Generuje string znacznika czasu."""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def backup_program_files(timestamp):
    """
    Tworzy backup plików programu do archiwum ZIP.

    Opis:
    Archiwizuje pliki z katalogu SCRIPT_DIR (zgodnie z FILES_TO_BACKUP_EXTENSIONS
    i z wyłączeniem FILES_TO_IGNORE_ON_BACKUP) do pliku .zip w katalogu backupów.

    Wpływ na inne funkcje:
    - Wykorzystuje ensure_backup_directory_exists.
    - Nazwa archiwum zawiera podany timestamp.
    """
    backup_dir = ensure_backup_directory_exists()
    if not backup_dir: return False

    archive_name = f"program_files_backup_{timestamp}.zip"
    archive_path = os.path.join(backup_dir, archive_name)

    logger.info(f"Rozpoczynam backup plików programu do: {archive_path}")
    try:
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(SCRIPT_DIR):
                # Ignorowanie folderów na podstawie ich nazw (dla folderów w SCRIPT_DIR)
                dirs[:] = [d for d in dirs if os.path.join(os.path.abspath(root), d) not in [os.path.join(SCRIPT_DIR, item) for item in FILES_TO_IGNORE_ON_BACKUP if os.path.isdir(os.path.join(SCRIPT_DIR, item))]]
                # Usuwamy również katalogi pasujące do wzorców (np. "backup_description_*.txt" nie jest katalogiem, ale zostawiamy ogólną logikę)
                dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, pattern) for pattern in FILES_TO_IGNORE_ON_BACKUP if "*" in pattern or "?" in pattern)]


                dirs[:] = [d for d in dirs if not d.startswith('.') and d != "__pycache__"] # Ogólne ignorowanie ukrytych i pycache

                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.abspath(file_path) == os.path.abspath(archive_path):
                        continue

                    should_ignore_file = False
                    relative_path = os.path.relpath(file_path, SCRIPT_DIR)
                    relative_path_parts = relative_path.split(os.sep)


                    # Sprawdź, czy plik lub jego katalog nadrzędny jest na liście ignorowanych (dokładne dopasowanie)
                    current_path_check = ""
                    for part in relative_path_parts:
                        current_path_check = os.path.join(current_path_check, part)
                        if current_path_check in FILES_TO_IGNORE_ON_BACKUP:
                            should_ignore_file = True
                            break
                    if relative_path_parts[-1] in FILES_TO_IGNORE_ON_BACKUP: # Sprawdź samą nazwę pliku
                        should_ignore_file = True
                    
                    # Sprawdź, czy plik pasuje do wzorców ignorowania
                    if not should_ignore_file:
                        for pattern in FILES_TO_IGNORE_ON_BACKUP:
                            if "*" in pattern or "?" in pattern: # Proste sprawdzenie czy to wzorzec
                                # Sprawdzamy dla pełnej relatywnej ścieżki
                                if fnmatch.fnmatch(relative_path, pattern):
                                    should_ignore_file = True
                                    break
                                # Sprawdzamy dla samej nazwy pliku
                                if fnmatch.fnmatch(file, pattern):
                                    should_ignore_file = True
                                    break
                    
                    if should_ignore_file:
                        # logger.debug(f"Ignoruję plik (na liście ignorowanych lub pasuje do wzorca): {file_path}")
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
    """
    Tworzy backup bazy danych MySQL oraz generuje plik tekstowy ze strukturą tabel bazy danych.

    Opis modyfikacji (wcześniejsza):
    Dodano generowanie pliku DB_STRUCTURE_FILE_NAME zawierającego strukturę tabel bazy danych.
    Plik ten jest tworzony w SCRIPT_DIR. Zmiana ta nie wpływa na podstawową logikę
    tworzenia głównego pliku backupu .sql ani na zwracaną wartość przez funkcję,
    która nadal odzwierciedla sukces/porażkę głównego backupu.
    Plik struktury został dodany do FILES_TO_IGNORE_ON_BACKUP.
    """
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

    main_backup_successful = False

    # --- Główny backup bazy danych (dane + struktura) ---
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

        logger.debug(f"Wykonywanie polecenia (pełny backup): {' '.join(final_command_list)}")
        process = subprocess.Popen(final_command_list, stdout=f_out, stderr=subprocess.PIPE, shell=False)
        stderr_output_bytes, _ = process.communicate()
        stderr_output = stderr_output_bytes.decode(errors='replace') if stderr_output_bytes else ""

        if process.returncode == 0:
            logger.info(f"Backup bazy danych '{db_name}' zakończony pomyślnie: {backup_filepath}")
            if stderr_output: logger.warning(f"Komunikaty z mysqldump (stderr - pełny backup):\n{stderr_output}")
            main_backup_successful = True
        else:
            error_message = f"Błąd podczas wykonywania mysqldump (pełny backup, kod: {process.returncode})."
            if stderr_output: error_message += f"\nKomunikat błędu mysqldump:\n{stderr_output}"
            logger.error(error_message)
            main_backup_successful = False
    except FileNotFoundError:
        logger.error(f"Nie znaleziono programu mysqldump. Ścieżka: '{MYSQLDUMP_PATH}'. Nie można wykonać pełnego backupu.")
        main_backup_successful = False
    except Exception as e:
        logger.error(f"Nieoczekiwany błąd podczas tworzenia pełnego backupu bazy danych: {e}", exc_info=True)
        main_backup_successful = False
    finally:
        if f_out: f_out.close()
        if process and process.returncode != 0 and os.path.exists(backup_filepath):
            try:
                logger.info(f"Próba usunięcia niekompletnego pliku pełnego backupu: {backup_filepath}")
                os.remove(backup_filepath)
            except Exception as e_rem:
                logger.error(f"Nie udało się usunąć niekompletnego pliku pełnego backupu {backup_filepath}: {e_rem}")

    # --- Backup struktury bazy danych do pliku tekstowego ---
    structure_backup_filepath = os.path.join(SCRIPT_DIR, DB_STRUCTURE_FILE_NAME)
    logger.info(f"Rozpoczynam tworzenie pliku struktury tabel bazy danych '{db_name}' do: {structure_backup_filepath}")

    structure_command = [MYSQLDUMP_PATH, f"--host={db_host}", f"--port={db_port}", f"--user={db_user}"]
    if db_password: structure_command.append(f"--password={db_password}")
    structure_command.extend(["--no-data", "--skip-triggers", "--skip-routines", "--skip-events", db_name])

    structure_process = None
    sf_out = None
    try:
        sf_out = open(structure_backup_filepath, 'w', encoding='utf-8')
        executable_path_struct = MYSQLDUMP_PATH
        if ' ' in executable_path_struct and not (executable_path_struct.startswith('"') and executable_path_struct.endswith('"')):
            executable_path_struct = f'"{executable_path_struct}"'
        final_structure_command_list = structure_command.copy()
        final_structure_command_list[0] = executable_path_struct

        logger.debug(f"Wykonywanie polecenia (struktura): {' '.join(final_structure_command_list)}")
        structure_process = subprocess.Popen(final_structure_command_list, stdout=sf_out, stderr=subprocess.PIPE, shell=False)
        s_stderr_output_bytes, _ = structure_process.communicate()
        s_stderr_output = s_stderr_output_bytes.decode(errors='replace') if s_stderr_output_bytes else ""

        if structure_process.returncode == 0:
            logger.info(f"Plik struktury tabel bazy danych '{db_name}' utworzony pomyślnie: {structure_backup_filepath}")
            if s_stderr_output: logger.warning(f"Komunikaty z mysqldump (stderr - struktura):\n{s_stderr_output}")
        else:
            error_message_struct = f"Błąd podczas tworzenia pliku struktury tabel (kod: {structure_process.returncode})."
            if s_stderr_output: error_message_struct += f"\nKomunikat błędu mysqldump (struktura):\n{s_stderr_output}"
            logger.error(error_message_struct)
    except FileNotFoundError:
        logger.error(f"Nie znaleziono programu mysqldump. Ścieżka: '{MYSQLDUMP_PATH}'. Nie można utworzyć pliku struktury tabel.")
    except Exception as e_struct:
        logger.error(f"Nieoczekiwany błąd podczas tworzenia pliku struktury tabel bazy danych: {e_struct}", exc_info=True)
    finally:
        if sf_out: sf_out.close()

    return main_backup_successful

def list_backup_sets():
    """
    Listuje dostępne kompletne zestawy backupów (pliki + baza danych) wraz z ich opisami.

    Opis modyfikacji:
    - Odczytuje pliki `backup_description_{timestamp}.txt` z katalogu backupów,
      aby dołączyć opisy do informacji o zestawach backupu.
    - Zaktualizowano słownik zwracany dla każdego zestawu, dodając klucz 'description'.

    Wpływ na inne funkcje:
    - Wynik tej funkcji jest używany przez `display_and_select_backup_set` do wyświetlenia
      listy backupów użytkownikowi.
    """
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
            description = ""
            desc_filename = f"backup_description_{ts}.txt"
            desc_filepath = os.path.join(backup_dir, desc_filename)
            if os.path.exists(desc_filepath):
                try:
                    with open(desc_filepath, 'r', encoding='utf-8') as f_desc:
                        description = f_desc.read().strip()
                except Exception as e_read_desc:
                    logger.warning(f"Nie udało się odczytać pliku opisu {desc_filepath}: {e_read_desc}")

            complete_sets.append({
                "timestamp_str": ts,
                "files_backup_name": data["files"],
                "db_backup_name": data["db"],
                "datetime_obj": data["datetime"],
                "description": description # Dodano opis
            })
    complete_sets.sort(key=lambda x: x["datetime_obj"], reverse=True)
    return complete_sets


def restore_program_files(zip_backup_path):
    """
    Przywraca pliki programu z podanego archiwum ZIP.

    Opis modyfikacji:
    - Dodano warunek, aby pliki z rozszerzeniem `.bat` znajdujące się bezpośrednio
      w `SCRIPT_DIR` nie były usuwane podczas etapu czyszczenia katalogu przed
      rozpakowaniem archiwum.

    Wpływ na inne funkcje:
    - Ta funkcja jest kluczowa dla procesu odtwarzania plików. Dodatkowa ochrona
      plików .bat zwiększa bezpieczeństwo użytkowania skryptu.
    """
    if not os.path.exists(zip_backup_path):
        logger.error(f"Plik backupu plików programu nie istnieje: {zip_backup_path}")
        return False

    logger.info(f"Rozpoczynam przywracanie plików programu z: {zip_backup_path}")

    preserved_full_paths = [os.path.join(SCRIPT_DIR, p_item) for p_item in FILES_TO_PRESERVE_ON_RESTORE]
    logger.debug(f"Elementy chronione przed usunięciem/nadpisaniem (z listy): {preserved_full_paths}")

    try:
        # Usuwanie starych plików z zachowaniem chronionych
        for item_name in os.listdir(SCRIPT_DIR):
            item_full_path = os.path.join(SCRIPT_DIR, item_name)

            # --- OCHRONA PLIKÓW .BAT ---
            if os.path.isfile(item_full_path) and item_name.lower().endswith(".bat"):
                logger.info(f"Pomijam usuwanie chronionego pliku .bat: {item_full_path}")
                continue
            # --- KONIEC OCHRONY PLIKÓW .BAT ---

            if item_full_path in preserved_full_paths or \
               any(item_full_path.startswith(preserved_path + os.sep) for preserved_path in preserved_full_paths if os.path.isdir(preserved_path)) :
                logger.debug(f"Pomijam usuwanie chronionego elementu (z listy FILES_TO_PRESERVE_ON_RESTORE): {item_full_path}")
                continue

            try:
                if os.path.isfile(item_full_path) or os.path.islink(item_full_path):
                    os.unlink(item_full_path)
                    logger.debug(f"Usunięto plik: {item_full_path}")
                elif os.path.isdir(item_full_path):
                    if item_name.lower() == ".git": # Dodatkowe zabezpieczenie
                        logger.info("Jawnie pomijam usuwanie katalogu .git (ponowne sprawdzenie).")
                        continue
                    shutil.rmtree(item_full_path, onerror=handle_rmtree_error)
                    logger.debug(f"Zakończono próbę usunięcia katalogu (lub jego zawartości): {item_full_path}")
            except Exception as e_del:
                logger.error(f"Błąd podczas usuwania '{item_full_path}': {e_del}. Kontynuuję z pozostałymi.")

        logger.info("Rozpakowywanie archiwum...")
        with zipfile.ZipFile(zip_backup_path, 'r') as zipf:
            for member in zipf.namelist():
                target_path = os.path.join(SCRIPT_DIR, member)
                is_preserved_target = False
                for preserved_item_name in FILES_TO_PRESERVE_ON_RESTORE:
                    preserved_full_item_path = os.path.join(SCRIPT_DIR, preserved_item_name)
                    if os.path.abspath(target_path) == os.path.abspath(preserved_full_item_path) or \
                       target_path.startswith(preserved_full_item_path + os.sep):
                        is_preserved_target = True
                        logger.debug(f"Pomijam nadpisywanie/tworzenie chronionego elementu '{member}' z archiwum (z listy FILES_TO_PRESERVE_ON_RESTORE).")
                        break
                
                # Dodatkowa ochrona przed nadpisaniem plików .bat z archiwum, jeśli istnieją i nie chcemy ich ruszać.
                # Obecnie logika jest taka, że jeśli .bat nie został usunięty, to może zostać nadpisany z archiwum,
                # jeśli nie jest na liście FILES_TO_PRESERVE_ON_RESTORE.
                # Jeśli pliki .bat mają być *nigdy* nieruszane przez archiwum, trzeba by dodać:
                # if os.path.isfile(target_path) and target_path.lower().endswith(".bat"):
                #     logger.info(f"Plik .bat '{target_path}' istnieje i nie zostanie nadpisany z archiwum.")
                #     continue
                # Jednak obecne żądanie dotyczyło tylko niekasowania ich.

                if not is_preserved_target:
                    try:
                        zipf.extract(member, SCRIPT_DIR)
                        logger.debug(f"Przywrócono plik z archiwum: {member}")
                    except Exception as e_extract:
                        logger.error(f"Błąd podczas rozpakowywania pliku '{member}': {e_extract}")
                else:
                    logger.debug(f"Plik '{member}' z archiwum wskazuje na chronioną ścieżkę (z listy), pomijam rozpakowanie.")


        logger.info(f"Pomyślnie zakończono operację przywracania plików programu z {zip_backup_path} do {SCRIPT_DIR}")
        return True
    except Exception as e:
        logger.error(f"Krytyczny błąd podczas przywracania plików programu: {e}", exc_info=True)
        return False

def handle_rmtree_error(func, path, exc_info):
    """Obsługa błędów dla shutil.rmtree, szczególnie dla PermissionError."""
    exc_type, exc_value, exc_tb = exc_info
    if isinstance(exc_value, PermissionError):
        logger.warning(f"Odmowa dostępu podczas usuwania '{path}' przez funkcję '{func.__name__}'. Plik/folder może być zablokowany. Kontynuuję.")
    else:
        logger.error(f"Błąd podczas usuwania '{path}' przez '{func.__name__}': {exc_value}")

def restore_mysql_database(sql_backup_path):
    # ... (ta funkcja pozostaje bez zmian w stosunku do poprzedniej wersji) ...
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
            if "Unknown database" not in stderr_drop and "Can't drop database" not in stderr_drop : # Akceptujemy te błędy
                logger.error(f"Błąd podczas usuwania bazy danych '{db_name}' (kod: {process_drop.returncode}). Komunikat: {stderr_drop}")
                return False
            else:
                logger.info(f"Baza '{db_name}' nie istniała lub nie można było jej usunąć (np. z powodu braku uprawnień, ale to może być OK jeśli zaraz ją tworzymy). Kontynuuję.")
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
    """
    Wyświetla listę dostępnych zestawów backupu i pozwala użytkownikowi wybrać jeden.

    Opis modyfikacji:
    - Wyświetla opis backupu, jeśli jest dostępny dla danego zestawu.

    Wpływ na inne funkcje:
    - Używana przez `handle_restore_set` do interakcji z użytkownikiem.
    """
    if not backup_sets:
        logger.info("Nie znaleziono żadnych kompletnych zestawów backupów (pliki + baza danych).")
        return None
    print("\nDostępne kompletne zestawy backupów (posortowane od najnowszych):")
    for i, backup_set in enumerate(backup_sets):
        print(f"  {i+1}. Data: {backup_set['datetime_obj'].strftime('%Y-%m-%d %H:%M:%S')}")
        if backup_set.get("description"):
            print(f"      Opis: {backup_set['description']}")
        print(f"      Pliki: {backup_set['files_backup_name']}")
        print(f"      Baza:  {backup_set['db_backup_name']}")
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
    """
    Obsługuje proces wyboru i przywracania zestawu backupu, pozwalając na selektywne odtwarzanie.

    Opis modyfikacji:
    - Po wybraniu zestawu backupu, pyta użytkownika, czy chce przywrócić tylko pliki,
      tylko bazę danych, czy oba komponenty.
    - Wywołuje odpowiednie funkcje przywracania (`restore_program_files` i/lub
      `restore_mysql_database`) na podstawie wyboru użytkownika.
    - Zaktualizowano logikę podsumowania operacji przywracania.

    Wpływ na inne funkcje:
    - Główna funkcja zarządzająca procesem przywracania.
    - Wykorzystuje `list_backup_sets`, `display_and_select_backup_set`,
      `restore_program_files`, `restore_mysql_database`.
    """
    logger.info(">>> Rozpoczynanie procesu przywracania z backupu <<<")
    backup_sets = list_backup_sets()
    if not backup_sets: return
    selected_set = display_and_select_backup_set(backup_sets)
    if not selected_set:
        logger.info("Nie wybrano zestawu backupu do przywrócenia.")
        return

    logger.warning("-" * 50)
    logger.warning("UWAGA: Wybrano przywracanie następującego zestawu backupu:")
    logger.warning(f"  Data: {selected_set['datetime_obj'].strftime('%Y-%m-%d %H:%M:%S')}")
    if selected_set.get("description"):
        logger.warning(f"  Opis: {selected_set['description']}")
    logger.warning(f"  Pliki programu z: {selected_set['files_backup_name']}")
    logger.warning(f"  Baza danych z:    {selected_set['db_backup_name']}")
    logger.warning("Operacja może NADPISAĆ bieżące pliki programu (z wyjątkiem chronionych)")
    logger.warning("oraz/lub CAŁKOWICIE USUNĄĆ i ZASTĄPIĆ bieżącą bazę danych.")
    logger.warning("-" * 50)
    
    if input("Czy na pewno chcesz kontynuować z wyborem tego zestawu? (tak/nie): ").lower() != 'tak':
        logger.info("Wybór zestawu backupu anulowany przez użytkownika.")
        return

    print("\nCo chcesz przywrócić z wybranego zestawu?")
    print("1. Tylko pliki programu")
    print("2. Tylko bazę danych")
    print("3. Zarówno pliki programu, jak i bazę danych (pełne przywracanie)")
    print("0. Anuluj operację przywracania")

    restore_choice = ""
    while restore_choice not in ['1', '2', '3', '0']:
        restore_choice = input("Wybierz opcję przywracania (0-3): ")
        if restore_choice not in ['1', '2', '3', '0']:
            print("Nieprawidłowy wybór. Wprowadź liczbę od 0 do 3.")

    if restore_choice == '0':
        logger.info("Przywracanie anulowane przez użytkownika na etapie wyboru komponentów.")
        return

    files_to_restore = False
    db_to_restore = False

    if restore_choice == '1': # Tylko pliki
        files_to_restore = True
        logger.info("Wybrano przywracanie: TYLKO PLIKI PROGRAMU.")
    elif restore_choice == '2': # Tylko baza
        db_to_restore = True
        logger.info("Wybrano przywracanie: TYLKO BAZA DANYCH.")
    elif restore_choice == '3': # Oba
        files_to_restore = True
        db_to_restore = True
        logger.info("Wybrano przywracanie: PEŁNE (PLIKI PROGRAMU I BAZA DANYCH).")

    files_restored_ok = True 
    db_restored_ok = True    

    if files_to_restore:
        logger.info("--- Rozpoczynanie przywracania plików programu ---")
        files_backup_path = os.path.join(BACKUP_BASE_PATH, selected_set["files_backup_name"])
        files_restored_ok = restore_program_files(files_backup_path)
        if files_restored_ok:
            logger.info("--- Przywracanie plików programu zakończone pomyślnie ---")
        else:
            logger.error("!!! Błąd podczas przywracania plików programu. Sprawdź logi. !!!")
            if db_to_restore: # Jeśli planowano też przywracanie bazy
                if input("Wystąpił błąd przywracania plików. Czy mimo to kontynuować z przywracaniem bazy danych? (tak/nie): ").lower() != 'tak':
                    logger.info("Przywracanie bazy danych anulowane po błędzie przywracania plików.")
                    db_to_restore = False # Anuluj przywracanie bazy

    if db_to_restore:
        logger.info("--- Rozpoczynanie przywracania bazy danych ---")
        db_backup_path = os.path.join(BACKUP_BASE_PATH, selected_set["db_backup_name"])
        db_restored_ok = restore_mysql_database(db_backup_path)
        if db_restored_ok:
            logger.info("--- Przywracanie bazy danych zakończone pomyślnie ---")
        else:
            logger.error("!!! Błąd podczas przywracania bazy danych. Sprawdź logi. Baza może być w niekonsystentnym stanie! !!!")

    # Podsumowanie
    any_restore_attempted = files_to_restore or db_to_restore
    all_attempted_ok = True
    if files_to_restore and not files_restored_ok:
        all_attempted_ok = False
    if db_to_restore and not db_restored_ok:
        all_attempted_ok = False
    
    if not any_restore_attempted:
        logger.info("Nie wykonano żadnych operacji przywracania (prawdopodobnie anulowano).")
    elif all_attempted_ok:
        if files_to_restore and db_to_restore:
            logger.info(">>> Pełne przywracanie (pliki i baza) z zestawu backupu zakończone pomyślnie. <<<")
        elif files_to_restore:
            logger.info(">>> Przywracanie plików programu zakończone pomyślnie. <<<")
        elif db_to_restore:
            logger.info(">>> Przywracanie bazy danych zakończone pomyślnie. <<<")
    else:
        logger.warning(">>> Proces przywracania zakończony z błędami. Sprawdź dokładnie logi. <<<")


def main_menu():
    """
    Główne menu aplikacji menedżera backupów.

    Opis modyfikacji:
    - Podczas tworzenia nowego backupu (opcja 1), pyta użytkownika o opcjonalny
      opis dla backupu.
    - Opis jest zapisywany do pliku `backup_description_{timestamp}.txt` w katalogu
      backupów, jeśli backup plików i bazy danych zakończył się sukcesem.

    Wpływ na inne funkcje:
    - Steruje głównym przepływem aplikacji.
    - Wywołuje funkcje tworzenia backupu, przywracania oraz listowania.
    """
    while True:
        print("\n--- Menedżer Backupów ---")
        print("1. Wykonaj pełny backup (pliki programu i baza danych)")
        print("2. Przywróć z kompletnego zestawu backupu")
        print("3. Wyjdź")
        choice = input("Wybierz opcję: ")
        if choice == '1':
            logger.info(">>> Rozpoczynanie procesu tworzenia nowego backupu <<<")
            current_timestamp = generate_timestamp()
            
            description = input("Wprowadź krótki opis dla tego backupu (opcjonalnie, naciśnij Enter aby pominąć): ").strip()

            files_ok = backup_program_files(current_timestamp)
            db_ok = False
            if files_ok: 
                db_ok = backup_mysql_database(current_timestamp)
            
            if files_ok and db_ok:
                if description:
                    backup_storage_dir = ensure_backup_directory_exists() 
                    if backup_storage_dir:
                        desc_filename = f"backup_description_{current_timestamp}.txt"
                        desc_filepath = os.path.join(backup_storage_dir, desc_filename)
                        try:
                            with open(desc_filepath, 'w', encoding='utf-8') as f_desc:
                                f_desc.write(description)
                            logger.info(f"Zapisano opis backupu do: {desc_filepath}")
                        except Exception as e_desc:
                            logger.error(f"Nie udało się zapisać opisu backupu: {e_desc}")
                    else:
                        logger.error("Nie można zapisać opisu, ponieważ katalog backupu nie istnieje lub nie udało się go utworzyć.")
                logger.info(">>> Wszystkie operacje tworzenia backupu zakończone pomyślnie! <<<")
            else:
                logger.error(">>> Wystąpiły błędy podczas tworzenia backupu. Sprawdź logi. Opis (jeśli podano) nie został zapisany. <<<")
        
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

    config_file_name_to_preserve = "config.json"
    try:
        if hasattr(config_handler, 'constants') and hasattr(config_handler.constants, 'CONFIG_FILENAME'):
            config_file_name_to_preserve = config_handler.constants.CONFIG_FILENAME
    except NameError: 
        logger.debug("config_handler.constants nie znaleziono, używam domyślnej nazwy 'config.json' do zachowania.")
    except AttributeError:
        logger.debug("Atrybut CONFIG_FILENAME nie znaleziony w config_handler.constants, używam domyślnej 'config.json'.")

    if "config.json" in FILES_TO_PRESERVE_ON_RESTORE and "config.json" != config_file_name_to_preserve:
        FILES_TO_PRESERVE_ON_RESTORE.remove("config.json")
    if config_file_name_to_preserve not in FILES_TO_PRESERVE_ON_RESTORE:
        FILES_TO_PRESERVE_ON_RESTORE.append(config_file_name_to_preserve)
    FILES_TO_PRESERVE_ON_RESTORE = list(set(FILES_TO_PRESERVE_ON_RESTORE))

    logger.debug(f"Pliki/foldery chronione podczas przywracania (z listy): {FILES_TO_PRESERVE_ON_RESTORE}")
    logger.info(f"Pliki .bat w katalogu głównym skryptu ({SCRIPT_DIR}) będą chronione przed usunięciem podczas przywracania plików.")
    main_menu()