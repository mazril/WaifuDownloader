<?php
// php_config.php

// Ustaw strefę czasową, jeśli nie jest ustawiona globalnie
date_default_timezone_set('Europe/Warsaw');

// === ŚCIEŻKI ===
// Zakładamy, że pliki PHP znajdują się w tym samym katalogu co skrypty Python
define('SCRIPT_DIR', __DIR__);
define('BASE_DATA_DIR_NAME', "Modelki");
define('BASE_DATA_DIR', SCRIPT_DIR . '/' . BASE_DATA_DIR_NAME);

// Pliki JSON
define('CONFIG_FILENAME', "config.json");
define('CONFIG_FILE_PATH', SCRIPT_DIR . '/' . CONFIG_FILENAME);

define('MODEL_GALLERIES_SUFFIX', "_galleries.json");

// === POPRAWKA TUTAJ ===
// Dodano brakującą definicję stałej
define('INCOMPLETE_GALLERIES_FILENAME', "douzupelnienia.json");
// Teraz linia 19 (poniżej) będzie działać poprawnie
define('INCOMPLETE_GALLERIES_FILE_PATH', BASE_DATA_DIR . '/' . INCOMPLETE_GALLERIES_FILENAME);

define('GLOBAL_STATE_FILENAME', "global_progress_state.json");
define('GLOBAL_STATE_FILE_PATH', BASE_DATA_DIR . '/' . GLOBAL_STATE_FILENAME);

// Pliki TXT
define('LIST_FILE_PATH', SCRIPT_DIR . '/lista.txt');

// Pliki statusu
define('STATUS_JSON_AGGREGATE_PATH', SCRIPT_DIR . '/status_aggregate.json');
define('STATUS_PHP_FILE_PATH', SCRIPT_DIR . '/status.php');

// Kolejka
define('PRIORITY_QUEUE_FILENAME', "priority_queue.json");
define('PRIORITY_QUEUE_FILE_PATH', BASE_DATA_DIR . '/' . PRIORITY_QUEUE_FILENAME);

// Bieżący status
define('CURRENT_STATUS_FILENAME', "current_status.json");
define('CURRENT_STATUS_FILE_PATH', SCRIPT_DIR . '/' . CURRENT_STATUS_FILENAME);

// Adres API
define('API_URL', 'api.php');

?>