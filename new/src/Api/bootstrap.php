<?php
$root = dirname(__DIR__, 2);
foreach (['php_config.php','php_db_config.php','php_utils.php'] as $f) { $p = $root . DIRECTORY_SEPARATOR . $f; if (file_exists($p)) require_once $p; }
if (!isset($pdo) && function_exists('get_db_connection')) { try { $pdo = get_db_connection(); } catch (Throwable $e) {} }
