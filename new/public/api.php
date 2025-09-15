<?php
// Bulletproof API router (v11): JSON-only + fatal error trap + built-in ping
// No HTML output under any circumstance.

// Headers first
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');

// Pre-flight
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

// Environment
error_reporting(E_ALL);
ini_set('display_errors', '0');
ini_set('log_errors', '1');

$root = dirname(__DIR__);
$logDir = $root . '/logs';
if (!is_dir($logDir)) { @mkdir($logDir, 0777, true); }
ini_set('error_log', $logDir . '/php_error.log');

// Catch fatal errors (parse/compile/runtime fatals)
register_shutdown_function(function() {
    $e = error_get_last();
    if ($e && in_array($e['type'], [E_ERROR, E_PARSE, E_CORE_ERROR, E_COMPILE_ERROR])) {
        // Clean any buffered output
        while (ob_get_level() > 0) { ob_end_clean(); }
        http_response_code(500);
        echo json_encode([
            'error' => 'Fatal error',
            'type' => $e['type'],
            'message' => $e['message'],
            'file' => $e['file'],
            'line' => $e['line'],
        ]);
    }
});

// Turn warnings/notices into exceptions
set_error_handler(function ($severity, $message, $file, $line) {
    if (!(error_reporting() & $severity)) return false;
    throw new ErrorException($message, 0, $severity, $file, $line);
});

// Start clean buffer
while (ob_get_level() > 0) { ob_end_clean(); }
ob_start();

$action = $_REQUEST['action'] ?? null;
if (!$action) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing action parameter']);
    exit;
}

$action = preg_replace('/[^a-zA-Z0-9_\-\.]/', '_', $action);

// Built-in actions (so test always works even bez pliku w actions/)
if ($action === 'ping') {
    echo json_encode(['pong' => true, 'ts' => time(), 'router' => 'v11']);
    $out = ob_get_contents(); ob_end_clean(); echo $out; exit;
}

// Bootstrap
$bootstrap = $root . '/src/Api/bootstrap.php';
if (file_exists($bootstrap)) {
    require_once $bootstrap;
} else {
    foreach (['php_config.php','php_db_config.php','php_utils.php'] as $f) {
        $p = $root . '/' . $f;
        if (file_exists($p)) require_once $p;
    }
}

// Resolve action file
$actionFile = $root . '/src/Api/actions/' . $action . '.php';
if (!file_exists($actionFile)) {
    http_response_code(404);
    echo json_encode(['error' => 'Unknown action', 'action' => $action]);
    $out = ob_get_contents(); ob_end_clean(); echo $out; exit;
}

try {
    require $actionFile;
    $out = ob_get_contents();
    ob_end_clean();
    if ($out === '' || $out === false) {
        echo json_encode(['ok' => true, 'action' => $action]);
    } else {
        $trim = ltrim($out);
        $first = $trim === '' ? '' : $trim[0];
        if ($first !== '{' && $first !== '[') {
            http_response_code(200);
            echo json_encode(['error' => 'Non-JSON output', 'raw' => $out, 'action' => $action]);
        } else {
            echo $out;
        }
    }
} catch (Throwable $e) {
    ob_end_clean();
    http_response_code(500);
    echo json_encode(['error' => 'Server error', 'message' => $e->getMessage(), 'action' => $action]);
}
