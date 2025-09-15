<?php
declare(strict_types=1);

// Force JSON-only output and trap PHP warnings/notices
ini_set('display_errors', '0');
error_reporting(E_ALL);

// Convert warnings/notices to exceptions so we can return JSON
set_error_handler(function ($severity, $message, $file, $line) {
    if (!(error_reporting() & $severity)) return false;
    throw new ErrorException($message, 0, $severity, $file, $line);
});

// Start clean output buffer to avoid stray HTML
while (ob_get_level() > 0) { ob_end_clean(); }
ob_start();
<?php
declare(strict_types=1);

// Common headers
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

// Bring in bootstrap (DB connection, utils, constants, etc.)
$root = dirname(__DIR__);
$bootstrap = $root . '/src/Api/bootstrap.php';
if (file_exists($bootstrap)) {
    require_once $bootstrap;
} else {
    // Fallback includes if bootstrap missing
    foreach (['php_config.php','php_db_config.php','php_utils.php'] as $f) {
        $p = $root . '/' . $f;
        if (file_exists($p)) require_once $p;
    }
}

// Resolve action
$action = $_REQUEST['action'] ?? null;
if (!$action) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing action parameter']);
    exit;
}

$action = preg_replace('/[^a-zA-Z0-9_\-\.]/', '_', $action);
$actionFile = $root . '/src/Api/actions/' . $action . '.php';

if (!file_exists($actionFile)) {
    http_response_code(404);
    echo json_encode(['error' => 'Unknown action', 'action' => $action]);
    exit;
}

// Execute action in current scope (has access to variables from bootstrap)

    try {
        require $actionFile;
        $out = ob_get_contents();
        ob_end_clean();
        if ($out === '' || $out === false) {
            echo json_encode(['ok' => true]);
        } else {
            // If output doesn't look like JSON, wrap it so frontend can still parse it
            $trim = ltrim($out);
            $first = $trim === '' ? '' : $trim[0];
            if ($first !== '{' && $first !== '[') {
                http_response_code(200);
                echo json_encode(['error' => 'Non-JSON output', 'raw' => $out]);
            } else {
                echo $out;
            }
        }
    } catch (Throwable $e) {
        ob_end_clean();
        http_response_code(500);
        echo json_encode(['error' => 'Server error', 'message' => $e->getMessage()]);
    }

