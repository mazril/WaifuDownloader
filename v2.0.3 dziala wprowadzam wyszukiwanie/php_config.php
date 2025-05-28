<?php
// php_config.php

date_default_timezone_set('Europe/Warsaw');

// Dołączenie konfiguracji bazy danych
require_once 'php_db_config.php'; // Upewnij się, że ten plik istnieje i jest poprawny

define('SCRIPT_DIR', __DIR__);
define('BASE_DATA_DIR_NAME', "Modelki"); // Używane tylko, jeśli skrypt PHP miałby dostęp do folderów z plikami
define('BASE_DATA_DIR', SCRIPT_DIR . '/' . BASE_DATA_DIR_NAME);

// Plik lista.txt jest nadal używany do dodawania nowych modelek przez interfejs PHP
define('LIST_FILE_PATH', SCRIPT_DIR . '/lista.txt');

// Adres API używany przez status.php
define('API_URL', 'api.php');

// Usunięto wszystkie definicje stałych odnoszące się do plików JSON, 
// które zostały zastąpione przez bazę danych, np.:
// CONFIG_FILENAME, CONFIG_FILE_PATH (plik konfiguracyjny Pythona, niepotrzebny w PHP w tym kontekście)
// MODEL_GALLERIES_SUFFIX
// INCOMPLETE_GALLERIES_FILENAME
// INCOMPLETE_GALLERIES_FILE_PATH
// GLOBAL_STATE_FILENAME
// GLOBAL_STATE_FILE_PATH
// STATUS_JSON_AGGREGATE_PATH
// PRIORITY_QUEUE_FILE_PATH
// CURRENT_STATUS_FILE_PATH

?>