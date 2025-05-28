# -*- coding: utf-8 -*-
import os

# === ŚCIEŻKI I NAZWY PLIKÓW ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DATA_DIR_NAME = "Modelki"
BASE_DATA_DIR = os.path.join(SCRIPT_DIR, BASE_DATA_DIR_NAME)

CONFIG_FILENAME = "config.json"
CONFIG_FILE_PATH = os.path.join(SCRIPT_DIR, CONFIG_FILENAME)

# Usunięto: MODEL_GALLERIES_SUFFIX
# Usunięto: INCOMPLETE_GALLERIES_FILENAME
# Usunięto: INCOMPLETE_GALLERIES_FILE_PATH
# Usunięto: GLOBAL_STATE_FILENAME
# Usunięto: GLOBAL_STATE_FILE_PATH
# Usunięto: STATUS_JSON_AGGREGATE_PATH
# Usunięto: PRIORITY_QUEUE_FILENAME
# Usunięto: PRIORITY_QUEUE_FILE_PATH
# Usunięto: CURRENT_STATUS_FILENAME
# Usunięto: CURRENT_STATUS_FILE_PATH

LIST_FILE_PATH = os.path.join(SCRIPT_DIR, 'lista.txt')
ADBLOCK_EXTENSION_PATH = os.path.join(SCRIPT_DIR, "uBlock0.chromium.ext.crx")
STATUS_PHP_FILE_PATH = os.path.join(SCRIPT_DIR, 'status.php') # Pozostaje, jeśli chcemy go znaleźć

# === USTAWIENIA ===
BASE_URL_SITE = "https://waifubitches.com"
NORDVPN_CLI_EXECUTABLE = "NordVPN.exe"
VERBOSE_VPN_LOGGING = True
MAX_DRIVER_STARTUP_ATTEMPTS = 3
DRIVER_STARTUP_TIMEOUT = 120
AI_MODEL_TO_USE = "google/flan-t5-large"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

# === WYJĄTKI ===
class RestartRequiredError(Exception):
    def __init__(self, message, no_vpn=False):
        super().__init__(message)
        self.no_vpn = no_vpn