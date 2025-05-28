# -*- coding: utf-8 -*-
import os

# === ŚCIEŻKI I NAZWY PLIKÓW ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DATA_DIR_NAME = "Modelki"
BASE_DATA_DIR = os.path.join(SCRIPT_DIR, BASE_DATA_DIR_NAME)

CONFIG_FILENAME = "config.json"
CONFIG_FILE_PATH = os.path.join(SCRIPT_DIR, CONFIG_FILENAME)

MODEL_GALLERIES_SUFFIX = "_galleries.json"
INCOMPLETE_GALLERIES_FILENAME = "douzupelnienia.json"
INCOMPLETE_GALLERIES_FILE_PATH = os.path.join(BASE_DATA_DIR, INCOMPLETE_GALLERIES_FILENAME)

GLOBAL_STATE_FILENAME = "global_progress_state.json"
GLOBAL_STATE_FILE_PATH = os.path.join(BASE_DATA_DIR, GLOBAL_STATE_FILENAME)

LIST_FILE_PATH = os.path.join(SCRIPT_DIR, 'lista.txt')
ADBLOCK_EXTENSION_PATH = os.path.join(SCRIPT_DIR, "uBlock0.chromium.ext.crx")

STATUS_JSON_AGGREGATE_PATH = os.path.join(SCRIPT_DIR, 'status_aggregate.json')
STATUS_HTML_FILE_PATH = os.path.join(SCRIPT_DIR, 'status.html')

PRIORITY_QUEUE_FILENAME = "priority_queue.json"
PRIORITY_QUEUE_FILE_PATH = os.path.join(BASE_DATA_DIR, PRIORITY_QUEUE_FILENAME)

CURRENT_STATUS_FILENAME = "current_status.json"
CURRENT_STATUS_FILE_PATH = os.path.join(SCRIPT_DIR, CURRENT_STATUS_FILENAME)

# === USTAWIENIA ===
BASE_URL_SITE = "https://waifubitches.com"
NORDVPN_CLI_EXECUTABLE = "NordVPN.exe"
VERBOSE_VPN_LOGGING = True
MAX_DRIVER_STARTUP_ATTEMPTS = 3
DRIVER_STARTUP_TIMEOUT = 120
AI_MODEL_TO_USE = "google/flan-t5-large"
# Usunięto HTTP_SERVER_HOST i HTTP_SERVER_PORT - przeniesione do config.json

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