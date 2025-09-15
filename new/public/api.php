<?php
// Bulletproof API router (v17): JSON-only + fatal error trap + request logging + built-in ping/diagnostics
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

error_reporting(E_ALL);
ini_set('display_errors', '0');
ini_set('log_errors', '1');

$root = dirname(__DIR__);
$logDir = $root . '/logs';
if (!is_dir($logDir)) { @mkdir($logDir, 0777, true); }
ini_set('error_log', $logDir . '/php_error.log');

register_shutdown_function(function() {
    $e = error_get_last();
    if ($e && in_array($e['type'], [E_ERROR, E_PARSE, E_CORE_ERROR, E_COMPILE_ERROR])) {
        while (ob_get_level() > 0) { ob_end_clean(); }
        http_response_code(500);
        echo json_encode(['error'=>'Fatal error','type'=>$e['type'],'message'=>$e['message'],'file'=>$e['file'],'line'=>$e['line']]);
    }
});

set_error_handler(function ($severity, $message, $file, $line) {
    if (!(error_reporting() & $severity)) return false;
    throw new ErrorException($message, 0, $severity, $file, $line);
});

while (ob_get_level() > 0) { ob_end_clean(); }
ob_start();

// Logger (with fallback to system temp if /logs is unwritable)
require_once $root . '/src/Api/lib/log.php';
if (!function_exists('api_log')) {
    function api_log($level, $message, $context=[]) {
        // fallback logger
        $entry = ['ts'=>date('c'),'level'=>$level,'message'=>$message,'context'=>$context];
        @file_put_contents(sys_get_temp_dir() . '/app.log', json_encode($entry) . PHP_EOL, FILE_APPEND);
    }
}

$action = $_REQUEST['action'] ?? null;
if (!$action) { http_response_code(400); echo json_encode(['error'=>'Missing action parameter']); exit; }
$action = preg_replace('/[^a-zA-Z0-9_\-\.]/', '_', $action);
api_log('request','API call',['action'=>$action,'method'=>$_SERVER['REQUEST_METHOD']??null,'get'=>$_GET??[],'post'=>$_POST??[]]);

// Built-in actions
if ($action === 'ping') { echo json_encode(['pong'=>true,'ts'=>time(),'router'=>'v17']); $out = ob_get_contents(); ob_end_clean(); echo $out; exit; }
if ($action === 'diagnostics') {
    echo json_encode(['ok'=>true,'diagnostics'=>[
        'script_name'=>$_SERVER['SCRIPT_NAME']??null,
        'request_uri'=>$_SERVER['REQUEST_URI']??null,
        'base_path_hint'=>rtrim(dirname($_SERVER['SCRIPT_NAME'] ?? ''), '/\\'),
        'server'=>['software'=>$_SERVER['SERVER_SOFTWARE']??null,'addr'=>$_SERVER['SERVER_ADDR']??null,'port'=>$_SERVER['SERVER_PORT']??null],
        'php'=>PHP_VERSION,'get'=>$_GET,'post'=>$_POST
    ]]); $out = ob_get_contents(); ob_end_clean(); echo $out; exit;
}

$bootstrap = $root . '/src/Api/bootstrap.php';
if (file_exists($bootstrap)) { require_once $bootstrap; }
else {
    foreach (['php_config.php','php_db_config.php','php_utils.php'] as $f) { $p = $root . '/' . $f; if (file_exists($p)) require_once $p; }
}

$actionFile = $root . '/src/Api/actions/' . $action . '.php';
if (!file_exists($actionFile)) { api_log('error','Unknown action',['action'=>$action]); http_response_code(404); echo json_encode(['error'=>'Unknown action','action'=>$action]); $out = ob_get_contents(); ob_end_clean(); echo $out; exit; }

try {
    require $actionFile;
    $out = ob_get_contents(); ob_end_clean();
    if ($out === '' || $out === false) {
        echo json_encode(['ok'=>true,'action'=>$action]);
    } else {
        $trim = ltrim($out); $first = $trim === '' ? '' : $trim[0];
        if ($first !== '{' && $first !== '[') {
            http_response_code(200);
            api_log('error','Non-JSON output',['action'=>$action,'preview'=>substr($out,0,400)]);
            echo json_encode(['error'=>'Non-JSON output','raw'=>$out,'action'=>$action]);
        } else {
            echo $out;
        }
    }
} catch (Throwable $e) {
    ob_end_clean();
    api_log('error','Exception',['action'=>$action,'message'=>$e->getMessage(),'file'=>$e->getFile(),'line'=>$e->getLine()]);
    http_response_code(500);
    echo json_encode(['error'=>'Server error','message'=>$e->getMessage(),'action'=>$action]);
}
