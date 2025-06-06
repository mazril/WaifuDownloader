# -*- coding: utf-8 -*-
import os

# === ŚCIEŻKI I NAZWY PLIKÓW ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DATA_DIR_NAME = "Modelki"
BASE_DATA_DIR = os.path.join(SCRIPT_DIR, BASE_DATA_DIR_NAME)

CONFIG_FILENAME = "config.json"
CONFIG_FILE_PATH = os.path.join(SCRIPT_DIR, CONFIG_FILENAME)

LIST_FILE_PATH = os.path.join(SCRIPT_DIR, 'lista.txt')
ADBLOCK_EXTENSION_PATH = os.path.join(SCRIPT_DIR, "uBlock0.chromium.ext.crx")
STATUS_PHP_FILE_PATH = os.path.join(SCRIPT_DIR, 'status.php')

# === USTAWIENIA ===
BASE_URL_SITE = "https://waifubitches.com"
NORDVPN_CLI_EXECUTABLE = "NordVPN.exe"
VERBOSE_VPN_LOGGING = True
MAX_DRIVER_STARTUP_ATTEMPTS = 3
DRIVER_STARTUP_TIMEOUT = 120

# --- Konfiguracja AI ---
# Usunięto OLLAMA_API_BASE_URL i OLLAMA_MODEL_NAME.
# Te wartości są teraz ładowane z config.json przez config_handler.py.

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