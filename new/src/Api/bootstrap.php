<?php
// Clean bootstrap for API actions.
// - Uses project root for includes
// - Safe to include multiple times
// - Initializes $pdo if not set and helper exists

$root = dirname(__DIR__, 2);

// Core includes
foreach (['php_config.php','php_db_config.php','php_utils.php'] as $f) {
    $p = $root . DIRECTORY_SEPARATOR . $f;
    if (file_exists($p)) {
        require_once $p;
    }
}

// Optional DB init
if (!isset($pdo) && function_exists('get_db_connection')) {
    try {
        $pdo = get_db_connection();
    } catch (Throwable $e) {
        // Router will capture/return this as JSON, but we leave it silent here
    }
}

// Place any constants that were previously defined in api.php preamble here if needed.
// (Intentionally minimal to avoid path/HTML issues.)
