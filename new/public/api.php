<?php
declare(strict_types=1);

// JSON-only, trap warnings
ini_set('display_errors', '0');
error_reporting(E_ALL);
set_error_handler(function ($severity, $message, $file, $line) {
    if (!(error_reporting() & $severity)) return false;
    throw new ErrorException($message, 0, $severity, $file, $line);
});

while (ob_get_level() > 0) { ob_end_clean(); }
ob_start();

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

$root = dirname(__DIR__);
$bootstrap = $root . '/src/Api/bootstrap.php';
if (file_exists($bootstrap)) {
    require_once $bootstrap;
} else {
    foreach (['php_config.php','php_db_config.php','php_utils.php'] as $f) {
        $p = $root . '/' . $f;
        if (file_exists($p)) require_once $p;
    }
}

$action = $_REQUEST['action'] ?? null;
if (!$action) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing action parameter']);
    return;
}

$action = preg_replace('/[^a-zA-Z0-9_\-\.]/', '_', $action);
$actionFile = $root . '/src/Api/actions/' . $action . '.php';
if (!file_exists($actionFile)) {
    http_response_code(404);
    echo json_encode(['error' => 'Unknown action', 'action' => $action]);
    return;
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
            echo json_encode(['error' => 'Non-JSON output', 'raw': $out, 'action' => $action]);
        } else {
            echo $out;
        }
    }
} catch (Throwable $e) {
    ob_end_clean();
    http_response_code(500);
    echo json_encode(['error' => 'Server error', 'message' => $e->getMessage(), 'action' => $action]);
}
