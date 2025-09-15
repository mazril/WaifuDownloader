<?php
<?php
// api.php




require_once 'php_config.php';
require_once 'php_utils.php';

// --- NOWA SEKCJA: USTAWIENIA CACHE ---
define('AGGREGATE_CACHE_DIR', __DIR__ . '/cache');
define('MODELS_CACHE_FILE', AGGREGATE_CACHE_DIR . '/models_list.json');
define('MODELS_CACHE_TIME', 300); // Czas ważności cache w sekundach (5 minut)

/**
 * Funkcja do czyszczenia pliku cache listy modeli.
 */
function clear_models_cache() {
    if (file_exists(MODELS_CACHE_FILE)) {
        @unlink(MODELS_CACHE_FILE);
        api_log("Cache listy modeli wyczyszczony.");
    }
}
// --- KONIEC SEKCJI CACHE ---


// Obsługa żądania OPTIONS (preflight)
if ($_SERVER['REQUEST_METHOD'] == 'OPTIONS') {
    http_response_code(200);
    exit();
}

// Definicja stałej dla limitu miniaturek
define('THUMBNAIL_LIMIT', 10);

// Funkcja logująca żądania API
function api_log($message) {
    $log_file = __DIR__ . '/api_debug.txt';
    $timestamp = date('Y-m-d H:i:s');
    $remote_addr = $_SERVER['REMOTE_ADDR'] ?? 'UNKNOWN_IP';
    $request_method = $_SERVER['REQUEST_METHOD'] ?? 'UNKNOWN_METHOD';
    $request_uri = $_SERVER['REQUEST_URI'] ?? 'UNKNOWN_URI';
    
    $log_entry = "[$timestamp] [Client: $remote_addr] [$request_method $request_uri] $message\n";
    file_put_contents($log_file, $log_entry, FILE_APPEND);
}

$action = $_GET['action'] ?? $_POST['action'] ?? null;
$response = ['success' => false, 'message' => 'Nieznana akcja lub brak akcji.'];
$pdo = get_db_connection();

if (!$pdo && !in_array($action, ['get_status', 'get_global_ai_settings', 'save_global_ai_settings', 'clear_cache'])) {
    http_response_code(503); 
    $response['message'] = 'Błąd serwera: Nie można połączyć się z bazą danych.';
    api_log("Krytyczny błąd: Brak połączenia PDO. Akcja: " . var_export($action, true));
    echo json_encode($response);
    exit();
}

$raw_post_data = file_get_contents('php://input');
if (
    ($_SERVER['REQUEST_METHOD'] === 'POST' && !empty($raw_post_data)) &&
    (
        !in_array($action, ['get_status', 'get_models_list', 'get_galleries_for_model', 'get_queue', 'clear_cache']) ||
        in_array($action, ['mark_gallery_completed', 'trigger_ai_test_run', 'trigger_ai_update', 'save_ai_prompt_config', 'rename_gallery_folder', 'update_queue', 'promote_test_to_production', 'save_global_ai_settings', 'toggle_gallery_disabled_status'])
    )
) {
    api_log("Akcja: " . var_export($action, true) . ", GET: " . json_encode($_GET) . ", POST_RAW: " . $raw_post_data);
} else {
    api_log("Akcja: " . var_export($action, true) . ", GET: " . json_encode($_GET));
}
