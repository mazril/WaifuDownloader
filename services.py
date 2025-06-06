# services.py
# -*- coding: utf-8 -*-
import time
import random
import requests
# import json # Nie jest już potrzebny bezpośrednio tutaj
import subprocess
import sys
# import re # Nie jest już potrzebny bezpośrednio tutaj
import logging
import os # Potrzebny dla download_image

import constants
import config_handler 
# import db_manager # Nie jest już potrzebny bezpośrednio tutaj, chyba że rotate_vpn/download_image by go używały

logger = logging.getLogger(__name__) # Standardowy logger dla funkcji w tym module

def rotate_vpn(attempts=3):
    """
    Przeprowadza rotację połączenia VPN za pomocą NordVPN CLI.
    Modyfikacja: Bez zmian funkcjonalnych, usunięto tylko niepotrzebne importy z modułu.
    """
    logger.info("Rozpoczynam rotację NordVPN...")
    for attempt in range(1, attempts + 1):
        try:
            logger.info(f"Próba rotacji VPN ({attempt}/{attempts})... Odłączam...")
            use_shell = sys.platform == "win32"
            disconnect_process = subprocess.run(
                [constants.NORDVPN_CLI_EXECUTABLE, "--disconnect"],
                capture_output=True, text=True, timeout=60, shell=use_shell, check=False
            )
            if disconnect_process.returncode != 0 and "You are not connected" not in disconnect_process.stderr:
                logger.warning(f"NordVPN disconnect stderr (kod {disconnect_process.returncode}): {disconnect_process.stderr.strip()}")
            time.sleep(random.uniform(3, 7))
            logger.info("Łączę z NordVPN...")
            connect_process = subprocess.run(
                [constants.NORDVPN_CLI_EXECUTABLE, "--connect"],
                capture_output=True, text=True, timeout=120, shell=use_shell, check=True
            )
            if constants.VERBOSE_VPN_LOGGING and connect_process.stdout: logger.debug(f"NordVPN connect stdout: {connect_process.stdout.strip()}")
            if connect_process.stderr: logger.warning(f"NordVPN connect stderr: {connect_process.stderr.strip()}")
            logger.info("Połączono. Czekam na stabilizację połączenia (10-15s)...")
            time.sleep(random.uniform(10, 15))
            logger.info("Weryfikuję nowe IP...")
            r = requests.get("https://api.ipify.org?format=json", timeout=20)
            r.raise_for_status()
            new_ip = r.json().get("ip", "Nie udało się odczytać IP")
            logger.info(f"Rotacja VPN zakończona pomyślnie! Nowe IP: {new_ip}")
            return True
        except subprocess.CalledProcessError as e: logger.error(f"Błąd polecenia NordVPN (próba {attempt}): {e.stderr.strip() if e.stderr else e.stdout.strip()}", exc_info=False)
        except subprocess.TimeoutExpired: logger.error(f"Timeout podczas operacji NordVPN (próba {attempt}).")
        except FileNotFoundError: logger.critical(f"BŁĄD: Plik wykonywalny '{constants.NORDVPN_CLI_EXECUTABLE}' nie został znaleziony."); return False
        except requests.RequestException as e: logger.error(f"Błąd weryfikacji IP po rotacji VPN (próba {attempt}): {e}", exc_info=False)
        except Exception as e: logger.error(f"Nieoczekiwany błąd podczas rotacji VPN (próba {attempt}): {e}", exc_info=True)
        if attempt < attempts: time.sleep(15)
    logger.error("Nie udało się wykonać rotacji VPN po wszystkich próbach."); return False

def download_image(url, dest_filepath):
    """
    Pobiera obrazek z podanego URL i zapisuje go w określonej ścieżce.
    Modyfikacja: Bez zmian funkcjonalnych, usunięto tylko niepotrzebne importy z modułu.
    """
    if config_handler.current_config is None: config_handler.load_config()
    cfg_downloading = config_handler.current_config.get('downloading', {})
    delay_min = cfg_downloading.get('download_delay_min', {}).get('value', 0.5)
    delay_max = cfg_downloading.get('download_delay_max', {}).get('value', 1.5)
    delay = random.uniform(delay_min, delay_max)
    time.sleep(delay)
    if os.path.exists(dest_filepath): logger.debug(f"Plik {os.path.basename(dest_filepath)} już istnieje."); return True
    logger.info(f"Pobieram {os.path.basename(dest_filepath)} z {url} (po {delay:.2f}s)...")
    try:
        headers = {'User-Agent': random.choice(constants.USER_AGENTS)}
        response = requests.get(url, stream=True, headers=headers, timeout=(10, 30))
        response.raise_for_status()
        with open(dest_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
        logger.debug(f"Pomyślnie pobrano {os.path.basename(dest_filepath)}."); return True
    except requests.exceptions.Timeout: logger.error(f"Timeout podczas pobierania {os.path.basename(dest_filepath)} z {url}.")
    except requests.exceptions.RequestException as ex: logger.error(f"Błąd żądania podczas pobierania {os.path.basename(dest_filepath)}: {ex}", exc_info=False)
    except Exception as ex_other: logger.error(f"Nieoczekiwany błąd podczas pobierania {os.path.basename(dest_filepath)}: {ex_other}", exc_info=True)
    if os.path.exists(dest_filepath):
        try: os.remove(dest_filepath); logger.info(f"Usunięto niekompletny plik {os.path.basename(dest_filepath)}.")
        except Exception as e_remove: logger.warning(f"Nie udało się usunąć niekompletnego pliku {os.path.basename(dest_filepath)}: {e_remove}")
    return False