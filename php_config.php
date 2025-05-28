<?php
// php_config.php

date_default_timezone_set('Europe/Warsaw');

require_once 'php_db_config.php'; // <--- DODANO

define('SCRIPT_DIR', __DIR__);
define('BASE_DATA_DIR_NAME', "Modelki");
define('BASE_DATA_DIR', SCRIPT_DIR . '/' . BASE_DATA_DIR_NAME);

// Usunięto definicje plików JSON (CONFIG_FILE_PATH pozostaje, jeśli jest używany gdzieś indziej, ale w tym kontekście nie jest)
// define('CONFIG_FILENAME', "config.json");
// define('CONFIG_FILE_PATH', SCRIPT_DIR . '/' . CONFIG_FILENAME);
// define('STATUS_JSON_AGGREGATE_PATH', SCRIPT_DIR . '/status_aggregate.json');
// define('PRIORITY_QUEUE_FILE_PATH', BASE_DATA_DIR . '/priority_queue.json');
// define('CURRENT_STATUS_FILE_PATH', SCRIPT_DIR . '/current_status.json');
// define('MODEL_GALLERIES_SUFFIX', "_galleries.json");

// Pozostaje tylko lista.txt
define('LIST_FILE_PATH', SCRIPT_DIR . '/lista.txt');
define('API_URL', 'api.php');

?>