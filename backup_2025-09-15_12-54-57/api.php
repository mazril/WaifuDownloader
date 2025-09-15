<?php
// api.php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

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


switch ($action) {
    case 'clear_cache':
        clear_models_cache();
        $response = ['success' => true, 'message' => 'Cache został wyczyszczony.'];
        break;

    case 'get_status':
        $status_data = get_app_state_db('current_status');
        if ($status_data && is_array($status_data)) {
            $defaults = [
                "timestamp" => date("Y-m-d H:i:s"), "message" => "Brak danych statusu.",
                "current_model" => "", "current_gallery_title" => "", "current_gallery_id" => null,
                "current_download_count" => null, "scan_session_found_count" => null,
                "current_expected_count" => null, "is_processing" => false
            ];
            $response = array_merge($defaults, $status_data);
        } else {
            $response = [
                "timestamp" => date("Y-m-d H:i:s"), "message" => "Oczekiwanie na pierwszy status ze skryptu Python (DB)...",
                "current_model" => "", "current_gallery_title" => "", "current_gallery_id" => null,
                "current_download_count" => null, "scan_session_found_count" => null,
                "current_expected_count" => null, "is_processing" => false
            ];
        }
        break;

    case 'get_queue':
        $queue_data = get_priority_queue_db(); 
        $response = $queue_data; 
        break;

    case 'get_models_list':
        if (file_exists(MODELS_CACHE_FILE) && (time() - filemtime(MODELS_CACHE_FILE) < MODELS_CACHE_TIME)) {
            api_log("Zwracam listę modeli z cache.");
            readfile(MODELS_CACHE_FILE);
            exit();
        }
        api_log("Generuję nową listę modeli (cache nie istnieje lub jest przestarzały).");

        $models_data = [];
        try {
            if (!$pdo) throw new Exception("Brak połączenia z bazą danych dla get_models_list.");

            $sql = "
                SELECT 
                    m.model_id, 
                    m.model_name, 
                    m.sanitized_name,
                    COUNT(g.gallery_id) as total_galleries,
                    SUM(CASE WHEN g.status IN ('completed', 'completed_with_tolerance') THEN 1 ELSE 0 END) as completed_galleries
                FROM models m
                LEFT JOIN galleries g ON m.model_id = g.model_id
                GROUP BY m.model_id, m.model_name, m.sanitized_name
                ORDER BY m.model_name ASC
            ";
            $stmt = $pdo->query($sql);
            $results = $stmt->fetchAll(PDO::FETCH_ASSOC);

            foreach ($results as $row) {
                $total = (int)$row['total_galleries'];
                $completed = (int)$row['completed_galleries'];
                $progress = ($total > 0) ? ($completed / $total * 100) : 0;

                $models_data[] = [
                    'model_name' => $row['model_name'],
                    'sanitized_name' => $row['sanitized_name'],
                    'total_galleries' => $total,
                    'completed_galleries' => $completed,
                    'model_progress' => $progress
                ];
            }
            
            $response = ['success' => true, 'models' => $models_data];

            if (!is_dir(AGGREGATE_CACHE_DIR)) {
                @mkdir(AGGREGATE_CACHE_DIR, 0775, true);
            }
            file_put_contents(MODELS_CACHE_FILE, json_encode($response), LOCK_EX);

        } catch (PDOException $e) {
            error_log("Błąd DB w get_models_list: " . $e->getMessage());
            api_log("Błąd DB w get_models_list: " . $e->getMessage());
            $response['message'] = 'Błąd pobierania listy modeli z bazy.';
            http_response_code(500);
        } catch (Exception $e) {
            error_log("Ogólny błąd w get_models_list: " . $e->getMessage());
            api_log("Ogólny błąd w get_models_list: " . $e->getMessage());
            $response['message'] = 'Błąd serwera przy pobieraniu listy modeli.';
            http_response_code(500);
        }
        break;

    case 'get_galleries_for_model':
        $model_name = $_GET['model_name'] ?? null;
        if (!$model_name) {
            $response['message'] = "Nie podano nazwy modelki.";
            http_response_code(400);
            break;
        }

        $galleries_data = [];
        try {
            if (!$pdo) throw new Exception("Brak połączenia z bazą danych dla get_galleries_for_model.");
            
            $stmt = $pdo->prepare("
                SELECT g.gallery_id, g.url, g.original_title, g.determined_title, 
                       g.folder_path, g.expected_count, g.downloaded_count, g.status, g.is_disabled,
                       m.model_name, m.sanitized_name AS model_sanitized_name
                FROM galleries g
                JOIN models m ON g.model_id = m.model_id
                WHERE m.model_name = :model_name
                ORDER BY COALESCE(g.determined_title, g.original_title, g.gallery_id) ASC
            ");
            $stmt->execute([':model_name' => $model_name]);
            $galleries = $stmt->fetchAll(PDO::FETCH_ASSOC);

            foreach ($galleries as $gallery_row) {
                $is_complete_status = in_array($gallery_row['status'], ["completed", "completed_with_tolerance"]);
                $expected = $gallery_row['expected_count'];
                $downloaded = $gallery_row['downloaded_count'];
                $status_color = $is_complete_status ? 'green' : ($downloaded > 0 ? 'orange' : 'red');
                
                $thumbnails = [];
                $web_path_segment = '';
                if (!empty($gallery_row['folder_path']) && is_dir($gallery_row['folder_path'])) {
                    $model_sanitized_name = $gallery_row['model_sanitized_name'];
                    $gallery_folder_name_only = basename($gallery_row['folder_path']);
                    $web_path_segment = (defined('BASE_DATA_DIR_NAME') ? BASE_DATA_DIR_NAME : "Modelki") . '/' . $model_sanitized_name . '/' . $gallery_folder_name_only;
                    
                    if (is_readable($gallery_row['folder_path'])) {
                        try {
                            $allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp'];
                            $files = [];
                            $dir_iterator = new DirectoryIterator($gallery_row['folder_path']);
                            foreach ($dir_iterator as $fileinfo) {
                                if ($fileinfo->isFile() && in_array(strtolower($fileinfo->getExtension()), $allowed_extensions)) {
                                    $files[] = $fileinfo->getFilename();
                                }
                            }
                            natsort($files);
                            $thumbnails = array_slice(array_values($files), 0, THUMBNAIL_LIMIT);
                        } catch (Exception $e) {
                            api_log("Błąd odczytu katalogu (iterator) dla miniaturek: " . $gallery_row['folder_path'] . " | Błąd: " . $e->getMessage());
                        }
                    } else {
                        api_log("Błąd odczytu katalogu (nieczytelny) dla miniaturek: " . $gallery_row['folder_path']);
                    }
                }

                $galleries_data[$gallery_row['gallery_id']] = [
                    'title' => $gallery_row['determined_title'] ?: $gallery_row['original_title'] ?: $gallery_row['gallery_id'],
                    'folder' => $gallery_row['folder_path'],
                    'expected' => $expected, 'downloaded' => $downloaded, 'url' => $gallery_row['url'],
                    'status_color' => $status_color, 'completed' => $is_complete_status,
                    'model_name' => $gallery_row['model_name'], 'gallery_id' => $gallery_row['gallery_id'],
                    'is_disabled' => (bool)$gallery_row['is_disabled'],
                    'thumbnails' => $thumbnails,
                    'web_path_segment' => $web_path_segment
                ];
            }
            $response = ['success' => true, 'galleries' => $galleries_data];
        
        } catch (PDOException $e) {
            error_log("Błąd DB w get_galleries_for_model: " . $e->getMessage());
            api_log("Błąd DB w get_galleries_for_model: " . $e->getMessage());
            $response['message'] = 'Błąd pobierania galerii dla modelki.';
            http_response_code(500);
        } catch (Exception $e) {
            error_log("Ogólny błąd w get_galleries_for_model: " . $e->getMessage());
            api_log("Ogólny błąd w get_galleries_for_model: " . $e->getMessage());
            $response['message'] = 'Błąd serwera przy pobieraniu galerii.';
            http_response_code(500);
        }
        break;

    case 'get_gallery_files':
        $gallery_id = $_GET['gallery_id'] ?? null;
        if (!$gallery_id) {
            $response['message'] = "Nie podano ID galerii.";
            break;
        }
        try {
            if (!$pdo) throw new Exception("Brak połączenia z bazą danych dla get_gallery_files.");
            $stmt = $pdo->prepare("
                SELECT g.folder_path, m.sanitized_name as model_sanitized_name
                FROM galleries g
                JOIN models m ON g.model_id = m.model_id
                WHERE g.gallery_id = :gallery_id
            ");
            $stmt->execute([':gallery_id' => $gallery_id]);
            $gallery_data_db = $stmt->fetch(PDO::FETCH_ASSOC); 

            if (!$gallery_data_db || empty($gallery_data_db['folder_path'])) {
                $response['message'] = "Nie znaleziono ścieżki folderu dla galerii o ID: " . htmlspecialchars($gallery_id) . " lub ścieżka jest pusta.";
                $response['success'] = true; 
                $response['files'] = [];
                $response['web_path_segment'] = ''; 
                break;
            }
            $absolute_folder_path = $gallery_data_db['folder_path'];
            $model_sanitized_name = $gallery_data_db['model_sanitized_name'];
            $gallery_folder_name_only = basename($absolute_folder_path);
            
            $web_path_segment = defined('BASE_DATA_DIR_NAME') ? BASE_DATA_DIR_NAME : "Modelki";
            $web_path_segment .= '/' . $model_sanitized_name . '/' . $gallery_folder_name_only;


            if (!is_dir($absolute_folder_path)) {
                $response['message'] = "Folder galerii nie istnieje na serwerze: " . htmlspecialchars($absolute_folder_path);
                $response['files'] = [];
                $response['web_path_segment'] = $web_path_segment;
                $response['success'] = true; 
                break;
            }
            $allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp'];
            $files = [];
            if (is_readable($absolute_folder_path)) {
                $dir_iterator = new DirectoryIterator($absolute_folder_path);
                foreach ($dir_iterator as $fileinfo) {
                    if ($fileinfo->isFile()) {
                        $extension = strtolower($fileinfo->getExtension());
                        if (in_array($extension, $allowed_extensions)) {
                            $files[] = $fileinfo->getFilename();
                        }
                    }
                }
                natsort($files); 
            } else {
                error_log("Nie można odczytać katalogu: " . $absolute_folder_path);
                api_log("Nie można odczytać katalogu: " . $absolute_folder_path);
                $response['message'] = "Nie można odczytać zawartości folderu galerii na serwerze.";
            }
             
            $response = [
                'success' => true,
                'files' => array_values($files), 
                'web_path_segment' => $web_path_segment,
                'gallery_id' => $gallery_id
            ];
        } catch (PDOException $e) {
            error_log("Błąd DB w get_gallery_files dla ID '$gallery_id': " . $e->getMessage());
            api_log("Błąd DB w get_gallery_files dla ID '$gallery_id': " . $e->getMessage());
            $response['message'] = "Błąd bazy danych podczas pobierania informacji o galerii.";
            http_response_code(500);
        } catch (Exception $e) {
            error_log("Inny błąd w get_gallery_files dla ID '$gallery_id': " . $e->getMessage());
            api_log("Inny błąd w get_gallery_files dla ID '$gallery_id': " . $e->getMessage());
            $response['message'] = "Wystąpił nieoczekiwany błąd serwera: " . $e->getMessage();
            http_response_code(500);
        }
        break;

    case 'rename_gallery_folder':
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
            $data_rename = json_decode($raw_post_data, true); 
            $gallery_id_rename = $data_rename['gallery_id'] ?? null;
            $new_title_rename = $data_rename['new_title'] ?? null;

            if (!$gallery_id_rename || $new_title_rename === null) {
                http_response_code(400); $response['message'] = 'Nie podano ID galerii lub nowego tytułu.'; break;
            }
            if (empty(trim($new_title_rename))) {
                 http_response_code(400); $response['message'] = 'Nowy tytuł nie może być pusty.'; break;
            }

            $status_data_rename = get_app_state_db('current_status'); 
            if ($status_data_rename && isset($status_data_rename['is_processing']) && $status_data_rename['is_processing'] && isset($status_data_rename['current_gallery_id']) && $status_data_rename['current_gallery_id'] == $gallery_id_rename) {
                $response['message'] = 'Galeria jest obecnie przetwarzana. Nie można zmienić nazwy folderu.'; break;
            }

            try {
                $pdo->beginTransaction();
                api_log("Rozpoczynam transakcję dla rename_gallery_folder: $gallery_id_rename");

                $stmt_update_title = $pdo->prepare("UPDATE galleries SET determined_title = :new_title WHERE gallery_id = :gallery_id"); 
                $stmt_update_title->execute([':new_title' => $new_title_rename, ':gallery_id' => $gallery_id_rename]);
                api_log("API rename: Zaktualizowano determined_title dla $gallery_id_rename na '$new_title_rename'.");

                $stmt_get_path = $pdo->prepare("
                    SELECT g.folder_path, m.sanitized_name as model_sanitized_name 
                    FROM galleries g 
                    JOIN models m ON g.model_id = m.model_id 
                    WHERE g.gallery_id = :gallery_id
                "); 
                $stmt_get_path->execute([':gallery_id' => $gallery_id_rename]);
                $gallery_path_data = $stmt_get_path->fetch(PDO::FETCH_ASSOC); 

                if (!$gallery_path_data) { 
                    api_log("API rename: Nie znaleziono galerii $gallery_id_rename.");
                    throw new Exception('Nie znaleziono galerii.'); 
                }
                
                $old_path = $gallery_path_data['folder_path'];
                api_log("API rename: Odczytana stara ścieżka: '$old_path'");

                $model_sanitized = $gallery_path_data['model_sanitized_name'];
                $new_gallery_sanitized = sanitize_foldername($new_title_rename);
                $script_base_dir_for_data = defined('BASE_DATA_DIR') ? BASE_DATA_DIR : (__DIR__ . '/' . (defined('BASE_DATA_DIR_NAME') ? BASE_DATA_DIR_NAME : 'Modelki'));
                $base_model_dir = rtrim($script_base_dir_for_data, '/') . '/' . $model_sanitized;
                $final_new_path = rtrim($base_model_dir, '/') . '/' . $new_gallery_sanitized; 

                $original_path_candidate = $final_new_path;
                $counter = 1;
                while (is_dir($final_new_path) && (!empty($old_path) && realpath($old_path) != realpath($final_new_path))) {
                    $final_new_path = $original_path_candidate . ' ' . $counter;
                    $counter++;
                }

                if ($original_path_candidate != $final_new_path) {
                    api_log("API rename: Wykryto duplikat dla '$original_path_candidate'. Nowa, unikalna ścieżka to: '$final_new_path'.");
                }

                if (empty($old_path)) {
                    api_log("API rename: Brak folder_path w DB dla $gallery_id_rename. Tylko aktualizacja tytułu. Nowa ścieżka w DB to '$final_new_path'");
                    $stmt_update_path_only = $pdo->prepare("UPDATE galleries SET folder_path = :new_path WHERE gallery_id = :gallery_id");
                    $stmt_update_path_only->execute([':new_path' => $final_new_path, ':gallery_id' => $gallery_id_rename]);
                    $pdo->commit();
                    $response = ['success' => true, 'message' => 'Tytuł zaktualizowany. Brak ścieżki folderu w bazie do zmiany nazwy.', 'new_folder_path' => $final_new_path];
                } else if (!is_dir($base_model_dir)) {
                    api_log("API rename: Katalog modelki '$base_model_dir' nie istnieje, próba utworzenia...");
                    if (!@mkdir($base_model_dir, 0775, true) && !is_dir($base_model_dir)) {
                        throw new Exception("Katalog modelki ($base_model_dir) nie istnieje i nie można go utworzyć.");
                    }
                } else if (is_dir($old_path) && realpath($old_path) == realpath($final_new_path)) {
                     $pdo->commit();
                     $response = ['success' => true, 'message' => 'Tytuł zaktualizowany. Nazwa folderu bez zmian.', 'new_folder_path' => $final_new_path];
                } elseif (!is_dir($old_path)) {
                    $stmt_update_path_db = $pdo->prepare("UPDATE galleries SET folder_path = :new_path WHERE gallery_id = :gallery_id"); 
                    $stmt_update_path_db->execute([':new_path' => $final_new_path, ':gallery_id' => $gallery_id_rename]);
                    $pdo->commit();
                    $response = ['success' => true, 'message' => "Tytuł zaktualizowany. Stary folder nie istniał. Zaktualizowano ścieżkę w DB.", 'new_folder_path' => $final_new_path];
                } else {
                    if (rename($old_path, $final_new_path)) {
                        $stmt_update_path_db_after_rename = $pdo->prepare("UPDATE galleries SET folder_path = :new_path WHERE gallery_id = :gallery_id"); 
                        $stmt_update_path_db_after_rename->execute([':new_path' => $final_new_path, ':gallery_id' => $gallery_id_rename]);
                        $pdo->commit();
                        $response = ['success' => true, 'message' => "Tytuł i folder zmienione na: " . basename($final_new_path), 'new_folder_path' => $final_new_path];
                    } else {
                        $pdo->rollBack();
                        $error = error_get_last();
                        $err_msg = $error ? $error['message'] : 'Nieznany błąd zmiany nazwy folderu.';
                        $response['message'] = "Nie udało się zmienić nazwy folderu na dysku. Błąd: $err_msg.";
                        api_log("Błąd zmiany nazwy folderu: $err_msg");
                    }
                }

                if ($response['success']) {
                    clear_models_cache();
                }

            } catch (PDOException $e) {
                if($pdo->inTransaction()) { $pdo->rollBack(); }
                $response['message'] = "Błąd bazy danych: " . $e->getMessage();
                http_response_code(500);
            } catch (Exception $e) {
                 if($pdo->inTransaction()) { $pdo->rollBack(); }
                $response['message'] = "Błąd serwera: " . $e->getMessage();
                http_response_code(500);
            }
        } else {
            http_response_code(405);
            $response['message'] = 'Metoda niedozwolona (wymagany POST).';
        }
        break;

    case 'update_queue':
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
            $new_queue_from_js = json_decode($raw_post_data, true); 

            if (is_array($new_queue_from_js)) {
                if (update_priority_queue_db($new_queue_from_js)) {
                    $response = ['success' => true, 'message' => 'Kolejka zaktualizowana w bazie danych.'];
                } else {
                    $response['message'] = 'Błąd zapisu kolejki do bazy danych.';
                    http_response_code(500);
                }
            } else {
                http_response_code(400);
                $response['message'] = 'Nieprawidłowe dane - oczekiwano listy (JSON array).';
            }
        } else {
            http_response_code(405);
            $response['message'] = 'Metoda niedozwolona (wymagany POST).';
        }
        break;

    case 'add_model':
        if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
        $model_name_param = trim($_GET['model_name'] ?? '');
        if (empty($model_name_param)) {
            $response['message'] = "Nie podano nazwy modelki.";
            http_response_code(400);
            break;
        }

        try {
            $sanitized_name = sanitize_foldername($model_name_param);
            
            $stmt_check = $pdo->prepare("SELECT model_id FROM models WHERE model_name = :model_name OR sanitized_name = :sanitized_name");
            $stmt_check->execute([':model_name' => $model_name_param, ':sanitized_name' => $sanitized_name]);
            if ($stmt_check->fetch()) {
                $response['message'] = "Modelka '$model_name_param' (lub jej znormalizowana forma) już istnieje w bazie danych.";
                $response['success'] = true; 
            } else {
                $stmt_insert = $pdo->prepare("INSERT INTO models (model_name, sanitized_name) VALUES (:model_name, :sanitized_name)");
                $stmt_insert->execute([':model_name' => $model_name_param, ':sanitized_name' => $sanitized_name]);
                if ($stmt_insert->rowCount() > 0) {
                    $response = ['success' => true, 'message' => "Modelka '$model_name_param' dodana do bazy danych."];
                    clear_models_cache();
                } else {
                    $response['message'] = "Nie udało się dodać modelki '$model_name_param' do bazy danych.";
                     http_response_code(500);
                }
            }
        } catch (PDOException $e) {
            error_log("Błąd DB w akcji add_model: " . $e->getMessage());
            api_log("Błąd DB w akcji add_model: " . $e->getMessage());
            $response['message'] = "Błąd bazy danych podczas dodawania modelki: " . $e->getMessage();
            http_response_code(500);
        }
        break;

    case 'prioritize':
        if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
        $type_param = $_GET['type'] ?? null;
        $id_param = $_GET['id'] ?? null;

        if ($type_param && $id_param) {
            $item_data_for_queue = null;
            $message = '';
            $added_successfully = false; 
            $operation_considered_successful = false; 

            if ($type_param === 'scan_model' || $type_param === 'scan_model_refresh_only') {
                $item_data_for_queue = $id_param; 
                if (add_to_priority_queue_db($type_param, $item_data_for_queue, true)) { 
                    $action_desc = ($type_param === 'scan_model_refresh_only') ? "odświeżania opisów" : "skanowania";
                    $message = "Zadanie $action_desc dla '$id_param' dodane na początek kolejki.";
                    $added_successfully = true;
                } else {
                   $message = "Zadanie dla '$id_param' już jest w kolejce lub wystąpił błąd dodawania. Sprawdź logi.";
                }
                $operation_considered_successful = true; 
            } elseif ($type_param === 'gallery') {
                $gallery_full_data_from_db = find_gallery_data_by_id_db($id_param); 
                if ($gallery_full_data_from_db) {
                    $item_data_for_queue = [
                        'id' => $gallery_full_data_from_db['id'],
                        'model_name' => $gallery_full_data_from_db['model_name'],
                        'title' => $gallery_full_data_from_db['title'],
                        'count' => $gallery_full_data_from_db['count'] ?? null,
                        'url' => $gallery_full_data_from_db['url'],
                        'fetch_mode' => 'full' 
                    ];
                    if (add_to_priority_queue_db('gallery', $item_data_for_queue, true)) { 
                        $message = "Galeria '{$item_data_for_queue['title']}' (model: {$item_data_for_queue['model_name']}) dodana na początek kolejki.";
                        $added_successfully = true;
                    } else {
                        $message = "Galeria '{$item_data_for_queue['title']}' już jest w kolejce lub wystąpił błąd dodawania. Sprawdź logi.";
                    }
                    $operation_considered_successful = true;
                } else {
                    $message = "Nie znaleziono danych dla galerii o ID '$id_param' w bazie danych.";
                }
            } else {
                $message = "Nieznany typ '$type_param' do priorytetyzacji.";
            }
            $response = ['success' => $operation_considered_successful, 'message' => $message];
        } else {
            $response['message'] = "Nie podano typu lub ID do priorytetyzacji.";
            http_response_code(400);
        }
        break;
    
    case 'search_galleries':
        if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
        $search_term = $_GET['term'] ?? '';
        if (empty($search_term)) {
            $response = ['success' => true, 'galleries' => []]; 
            break;
        }

        $galleries = [];
        try {
            $sql = "SELECT g.gallery_id, g.url, g.original_title, g.determined_title, 
                           g.expected_count, g.downloaded_count, g.status,
                           m.model_name, m.sanitized_name as model_sanitized_name
                     FROM galleries g
                     JOIN models m ON g.model_id = m.model_id
                     WHERE g.original_title LIKE ? 
                       OR g.determined_title LIKE ?
                       OR g.gallery_id LIKE ? 
                       OR m.model_name LIKE ?
                     ORDER BY 
                        m.model_name ASC, 
                        COALESCE(
                           CONVERT(g.determined_title USING utf8mb4), 
                           CONVERT(g.original_title USING utf8mb4), 
                           CONVERT(g.gallery_id USING utf8mb4)
                        ) ASC
                     LIMIT 100"; 

            $stmt = $pdo->prepare($sql);
            $term_param = '%' . $search_term . '%';
            $stmt->execute([$term_param, $term_param, $term_param, $term_param]);
            $results = $stmt->fetchAll(PDO::FETCH_ASSOC);

            foreach ($results as $row) {
                $is_complete_status = in_array($row['status'], ["completed", "completed_with_tolerance"]);
                $galleries[] = [
                    'gallery_id' => $row['gallery_id'],
                    'title' => $row['determined_title'] ?: $row['original_title'] ?: $row['gallery_id'],
                    'url' => $row['url'],
                    'model_name' => $row['model_name'],
                    'model_sanitized_name' => $row['model_sanitized_name'],
                    'expected' => $row['expected_count'],
                    'downloaded' => $row['downloaded_count'],
                    'status_color' => $is_complete_status ? 'green' : ($row['downloaded_count'] > 0 ? 'orange' : 'red'),
                    'completed' => $is_complete_status
                ];
            }
            $response = ['success' => true, 'galleries' => $galleries];

        } catch (PDOException $e) {
            error_log("Błąd DB w search_galleries: " . $e->getMessage());
            api_log("Błąd DB w search_galleries: " . $e->getMessage());
            $response['message'] = "Błąd bazy danych podczas wyszukiwania galerii.";
            http_response_code(500);
        }
        break;

    case 'refresh_empty_descriptions_all':
        if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
        try {
            $stmt = $pdo->query("SELECT model_name FROM models ORDER BY model_name ASC");
            $all_models = $stmt->fetchAll(PDO::FETCH_COLUMN);
            
            $added_count = 0;
            $skipped_count = 0;
            foreach ($all_models as $model_name) {
                if(add_to_priority_queue_db('scan_model_refresh_only', $model_name, false)) { 
                    $added_count++;
                } else {
                    $skipped_count++;
                }
            }
            $message = "Dodano $added_count modeli do kolejki odświeżania opisów.";
            if($skipped_count > 0) $message .= " Pominięto $skipped_count (prawdopodobnie już w kolejce).";
            $response = ['success' => true, 'message' => $message];

        } catch (PDOException $e) {
            error_log("Błąd DB w refresh_empty_descriptions_all: " . $e->getMessage());
            api_log("Błąd DB w refresh_empty_descriptions_all: " . $e->getMessage());
            $response['message'] = "Błąd bazy danych podczas dodawania zadań odświeżania.";
            http_response_code(500);
        }
        break;

    case 'refresh_all_galleries_lists':
        if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
        try {
            // Pobierz modele, które nie mają żadnych galerii w bazie (całkowicie puste modele)
            $stmt_empty_models = $pdo->query("
                SELECT m.model_name
                FROM models m
                LEFT JOIN galleries g ON m.model_id = g.model_id
                GROUP BY m.model_id
                HAVING COUNT(g.gallery_id) = 0
                ORDER BY m.model_name ASC
            ");
            $empty_models = $stmt_empty_models->fetchAll(PDO::FETCH_COLUMN);

            // Pobierz wszystkie pozostałe modele
            $stmt_other_models = $pdo->query("
                SELECT m.model_name
                FROM models m
                LEFT JOIN galleries g ON m.model_id = g.model_id
                GROUP BY m.model_id
                HAVING COUNT(g.gallery_id) > 0
                ORDER BY m.model_name ASC
            ");
            $other_models = $stmt_other_models->fetchAll(PDO::FETCH_COLUMN);
            
            $added_count = 0;
            $skipped_count = 0;

            // Najpierw dodaj puste modele na początek kolejki
            foreach ($empty_models as $model_name) {
                if (add_to_priority_queue_db('scan_model', $model_name, true)) {
                    $added_count++;
                } else {
                    $skipped_count++;
                }
            }

            // Następnie dodaj pozostałe modele (na koniec)
            foreach ($other_models as $model_name) {
                if (add_to_priority_queue_db('scan_model', $model_name, false)) {
                    $added_count++;
                } else {
                    $skipped_count++;
                }
            }

            $message = "Dodano $added_count modeli do kolejki skanowania galerii (najpierw puste, potem istniejące).";
            if($skipped_count > 0) $message .= " Pominięto $skipped_count (prawdopodobnie już w kolejce).";
            $response = ['success' => true, 'message' => $message];
            clear_models_cache(); 

        } catch (PDOException $e) {
            error_log("Błąd DB w refresh_all_galleries_lists: " . $e->getMessage());
            api_log("Błąd DB w refresh_all_galleries_lists: " . $e->getMessage());
            $response['message'] = "Błąd bazy danych podczas dodawania zadań skanowania.";
            http_response_code(500);
        }
        break;


    case 'get_galleries_for_ai_test':
        if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
        $model_filter = $_GET['model'] ?? '';
        $status_filter = $_GET['status_filter'] ?? '';
        $limit = isset($_GET['limit']) ? (int)$_GET['limit'] : 50; 
        $offset = isset($_GET['offset']) ? (int)$_GET['offset'] : 0;
        $sort_by = $_GET['sort_by'] ?? 'model_gallery';
        $sort_order = $_GET['sort_order'] ?? 'ASC';
        if (!in_array(strtoupper($sort_order), ['ASC', 'DESC'])) {
            $sort_order = 'ASC';
        }

        try {
            $base_select_sql = "SELECT g.gallery_id, g.original_title, g.determined_title, g.test_ai_title, g.folder_path, g.status, m.model_name ";
            $base_from_sql = "FROM galleries g JOIN models m ON g.model_id = m.model_id";
            
            $where_clauses = [];
            $execute_params_where = [];

            if (!empty($model_filter)) {
                $where_clauses[] = "m.model_name = :model_filter";
                $execute_params_where[':model_filter'] = $model_filter;
            }
            if (!empty($status_filter)) {
                $where_clauses[] = "g.status = :status_filter";
                $execute_params_where[':status_filter'] = $status_filter;
            }

            $where_sql = "";
            if (!empty($where_clauses)) {
                $where_sql = " WHERE " . implode(" AND ", $where_clauses);
            }

            $count_sql = "SELECT COUNT(*) " . $base_from_sql . $where_sql;
            $stmt_count = $pdo->prepare($count_sql);
            $stmt_count->execute($execute_params_where);
            $total_count = $stmt_count->fetchColumn();

            $order_by_map = [
                'model_gallery' => 'm.model_name ' . $sort_order . ', COALESCE(g.determined_title, g.original_title, g.gallery_id) ' . $sort_order,
                'original_title' => 'g.original_title ' . $sort_order,
                'determined_title' => 'g.determined_title ' . $sort_order,
                'test_ai_title' => 'g.test_ai_title ' . $sort_order,
                'status' => 'g.status ' . $sort_order
            ];
            $order_by_clause = $order_by_map[$sort_by] ?? $order_by_map['model_gallery'];

            $data_sql = $base_select_sql . $base_from_sql . $where_sql
                      . " ORDER BY " . $order_by_clause
                      . " LIMIT :limit OFFSET :offset";

            $stmt = $pdo->prepare($data_sql);
            
            foreach ($execute_params_where as $key => $val) {
               $stmt->bindValue($key, $val);
            }
            $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
            $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);

            $stmt->execute();
            $results = $stmt->fetchAll(PDO::FETCH_ASSOC);
            
            $response = ['success' => true, 'galleries' => $results, 'total' => (int)$total_count];

        } catch (PDOException $e) {
            error_log("Błąd DB w get_galleries_for_ai_test: " . $e->getMessage() . " | SQL: " . ($data_sql ?? "N/A"));
            api_log("Błąd DB w get_galleries_for_ai_test: " . $e->getMessage());
            $response['message'] = "Błąd bazy danych: " . $e->getMessage();
            http_response_code(500);
        }
        break;

    case 'trigger_ai_update': 
       if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
            $data_ai_update = json_decode($raw_post_data, true); 
            $gallery_id_ai_update = $data_ai_update['gallery_id'] ?? null; 

            if (!$gallery_id_ai_update) { http_response_code(400); $response['message'] = 'Nie podano ID galerii.'; break; }
            
            $op_success_ai_update = true; 
            $message_for_user_ai_update = ''; 
            $new_status_for_gallery_ai_update = ''; 

            try {
                $stmt_info_ai_update = $pdo->prepare("SELECT g.initial_data_fetched, g.url, m.model_name FROM galleries g JOIN models m ON g.model_id = m.model_id WHERE g.gallery_id = :gallery_id"); 
                $stmt_info_ai_update->execute([':gallery_id' => $gallery_id_ai_update]);
                $gallery_info_ai_update = $stmt_info_ai_update->fetch(PDO::FETCH_ASSOC); 

                if (!$gallery_info_ai_update) { 
                    $message_for_user_ai_update = 'Nie znaleziono galerii.'; 
                    http_response_code(404); 
                    $op_success_ai_update = false;
                } else {
                    if (!$gallery_info_ai_update['initial_data_fetched']) {
                        $task_payload_ai_update = [ 
                            'id' => $gallery_id_ai_update,
                            'model_name' => $gallery_info_ai_update['model_name'],
                            'url' => $gallery_info_ai_update['url'],
                            'fetch_mode' => 'initial_data_only',
                            'trigger_action_after_fetch' => 'production_ai'
                        ];
                        if (add_to_priority_queue_db('gallery', $task_payload_ai_update, true)) {
                            $new_status_for_gallery_ai_update = 'pending_initial_fetch_prod_ai';
                            $message_for_user_ai_update = "Zadanie pobrania danych inicjalnych i analizy AI (produkcyjne) dla '$gallery_id_ai_update' dodane do kolejki.";
                            api_log("API: Dodano zadanie 'gallery' (initial_data_only, trigger: production_ai) dla $gallery_id_ai_update.");
                        } else {
                            $message_for_user_ai_update = "Nie udało się dodać zadania pobrania danych dla '$gallery_id_ai_update' do kolejki (możliwy duplikat lub błąd DB).";
                            $op_success_ai_update = false; 
                        }
                    } else {
                        $new_status_for_gallery_ai_update = 'pending_production_ai';
                        $message_for_user_ai_update = "Zadanie analizy AI (produkcyjnej) dla '$gallery_id_ai_update' czeka na wykonanie przez worker AI.";
                        api_log("API: Ustawiono status 'pending_production_ai' dla $gallery_id_ai_update.");
                    }

                    if ($op_success_ai_update && !empty($new_status_for_gallery_ai_update)) {
                        $stmt_status_prod_ai = $pdo->prepare("UPDATE galleries SET status = :status, determined_title = NULL WHERE gallery_id = :gallery_id"); 
                        $stmt_status_prod_ai->execute([':status' => $new_status_for_gallery_ai_update, ':gallery_id' => $gallery_id_ai_update]);
                        api_log("Zaktualizowano status galerii $gallery_id_ai_update na '$new_status_for_gallery_ai_update' i wyczyszczono determined_title.");
                    } elseif ($op_success_ai_update && empty($new_status_for_gallery_ai_update)) {
                        $message_for_user_ai_update = "Nie udało się ustalić nowego statusu dla analizy AI produkcyjnej dla '$gallery_id_ai_update'.";
                        $op_success_ai_update = false;
                    }
                }
                $response = ['success' => $op_success_ai_update, 'message' => $message_for_user_ai_update];

            } catch (PDOException $e) { 
                error_log("Błąd DB w trigger_ai_update: " . $e->getMessage());
                api_log("Błąd DB w trigger_ai_update: " . $e->getMessage());
                $response['message'] = "Błąd bazy danych."; 
                http_response_code(500);
            }
       } else { 
            http_response_code(405);
            $response['message'] = 'Metoda niedozwolona (wymagany POST).';
       }
        break;

   case 'trigger_ai_test_run': 
       if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            if (!$pdo) { 
                $response['message'] = 'Brak połączenia z DB.'; 
                http_response_code(503); 
                api_log("trigger_ai_test_run: Brak połączenia PDO na początku akcji.");
                break; 
            }
            $data_test_ai = json_decode($raw_post_data, true); 
            $gallery_id_test_ai = $data_test_ai['gallery_id'] ?? null; 

            api_log("trigger_ai_test_run: Rozpoczęto akcję dla gallery_id: " . var_export($gallery_id_test_ai, true));

            if (!$gallery_id_test_ai) { 
                http_response_code(400); 
                $response['message'] = 'Nie podano ID galerii.'; 
                api_log("trigger_ai_test_run: Błąd - Nie podano ID galerii.");
                break; 
            }

            $op_success_test_ai = true; 
            $message_for_user_test_ai = ''; 
            $new_status_for_gallery_test_ai = ''; 

            try {
                api_log("trigger_ai_test_run: Próba pobrania informacji o galerii $gallery_id_test_ai z bazy.");
                $stmt_check_test_ai = $pdo->prepare("SELECT g.gallery_id, g.status as current_status_in_db, g.initial_data_fetched, g.url, m.model_name FROM galleries g JOIN models m ON g.model_id = m.model_id WHERE gallery_id = :gallery_id");
                $stmt_check_test_ai->execute([':gallery_id' => $gallery_id_test_ai]);
                $gallery_info_test_ai = $stmt_check_test_ai->fetch(PDO::FETCH_ASSOC);

                if (!$gallery_info_test_ai) { 
                    $message_for_user_test_ai = 'Nie znaleziono galerii o podanym ID.'; 
                    http_response_code(404); 
                    $op_success_test_ai = false;
                    api_log("trigger_ai_test_run: Nie znaleziono galerii $gallery_id_test_ai w bazie.");
                } else {
                    api_log("trigger_ai_test_run: Galeria $gallery_id_test_ai znaleziona. Aktualny status w DB przed operacją: '" . $gallery_info_test_ai['current_status_in_db'] . "'. Initial_fetched: " . ($gallery_info_test_ai['initial_data_fetched'] ? 'TRUE' : 'FALSE'));

                    if (!$gallery_info_test_ai['initial_data_fetched']) {
                        api_log("trigger_ai_test_run: Galeria $gallery_id_test_ai ma initial_data_fetched = FALSE. Przygotowuję zadanie dla Pythona.");
                        $task_payload_test_ai = [
                            'id' => $gallery_id_test_ai,
                            'model_name' => $gallery_info_test_ai['model_name'],
                            'url' => $gallery_info_test_ai['url'],
                            'fetch_mode' => 'initial_data_only',
                            'trigger_action_after_fetch' => 'test_ai'
                        ];
                        if (add_to_priority_queue_db('gallery', $task_payload_test_ai, true)) {
                            $new_status_for_gallery_test_ai = 'pending_initial_fetch_test_ai';
                            $message_for_user_test_ai = "Zadanie pobrania danych inicjalnych i testu AI dla '$gallery_id_test_ai' dodane do kolejki.";
                            api_log("trigger_ai_test_run: Dodano zadanie 'gallery' (initial_data_only, trigger: test_ai) dla $gallery_id_test_ai do kolejki Pythona. Ustawiam status na '$new_status_for_gallery_test_ai'.");
                        } else {
                            $message_for_user_test_ai = "Nie udało się dodać zadania pobrania danych dla testu AI dla '$gallery_id_test_ai' do kolejki (możliwy duplikat lub błąd DB).";
                            $op_success_test_ai = false;
                            api_log("trigger_ai_test_run: Błąd - Nie udało się dodać zadania dla $gallery_id_test_ai do kolejki Pythona.");
                        }
                    } else {
                        $new_status_for_gallery_test_ai = 'pending_test_ai';
                        $message_for_user_test_ai = "Zadanie testu AI dla '$gallery_id_test_ai' czeka na wykonanie przez worker AI (dane inicjalne już pobrane).";
                        api_log("trigger_ai_test_run: Galeria $gallery_id_test_ai ma initial_data_fetched = TRUE. Ustawiam status na '$new_status_for_gallery_test_ai'.");
                    }

                    if ($op_success_test_ai && !empty($new_status_for_gallery_test_ai)) {
                        api_log("trigger_ai_test_run: Przed UPDATE dla $gallery_id_test_ai. Planowany nowy status: '$new_status_for_gallery_test_ai'. test_ai_title zostanie ustawiony na NULL.");
                        
                        $stmt_status_update_test_ai = $pdo->prepare("UPDATE galleries SET status = :status, test_ai_title = NULL WHERE gallery_id = :gallery_id");
                        $stmt_status_update_test_ai->execute([':status' => $new_status_for_gallery_test_ai, ':gallery_id' => $gallery_id_test_ai]);
                        $rowCount_test_ai = $stmt_status_update_test_ai->rowCount();
                        
                        $stmt_verify_test_ai = $pdo->prepare("SELECT status FROM galleries WHERE gallery_id = :gallery_id");
                        $stmt_verify_test_ai->execute([':gallery_id' => $gallery_id_test_ai]);
                        $status_after_update_in_db_test_ai = $stmt_verify_test_ai->fetchColumn();

                        api_log("trigger_ai_test_run: Po UPDATE dla $gallery_id_test_ai. Status w DB odczytany jako: '$status_after_update_in_db_test_ai'. Zamierzony status: '$new_status_for_gallery_test_ai'. Liczba zmienionych wierszy przez UPDATE: $rowCount_test_ai.");
                        
                        if (strval($status_after_update_in_db_test_ai) !== strval($new_status_for_gallery_test_ai)) {
                            api_log("trigger_ai_test_run: KRYTYCZNY PROBLEM! Status w DB ('$status_after_update_in_db_test_ai') po wykonaniu UPDATE różni się od zamierzonego ('$new_status_for_gallery_test_ai') dla galerii $gallery_id_test_ai!");
                        }
                    } elseif ($op_success_test_ai && empty($new_status_for_gallery_test_ai)) {
                         $message_for_user_test_ai = "Nie udało się ustalić nowego statusu dla testu AI dla '$gallery_id_test_ai'.";
                         api_log("trigger_ai_test_run: BŁĄD LOGICZNY - Brak new_status_for_gallery_test_ai mimo op_success_test_ai=true dla $gallery_id_test_ai.");
                         $op_success_test_ai = false;
                    }
                }
                $response = ['success' => $op_success_test_ai, 'message' => $message_for_user_test_ai];

            } catch (PDOException $e) {
                error_log("Błąd PDO w trigger_ai_test_run dla ID '$gallery_id_test_ai': " . $e->getMessage());
                api_log("Błąd PDO w trigger_ai_test_run dla ID '$gallery_id_test_ai': " . $e->getMessage() . " | SQLState: " . $e->getCode() . " | Trace: " . $e->getTraceAsString());
                $response['message'] = "Błąd bazy danych: " . $e->getMessage(); 
                http_response_code(500);
            } catch (Exception $e) {
                error_log("Ogólny błąd w trigger_ai_test_run dla ID '$gallery_id_test_ai': " . $e->getMessage());
                api_log("Ogólny błąd w trigger_ai_test_run dla ID '$gallery_id_test_ai': " . $e->getMessage() . " | Trace: " . $e->getTraceAsString());
                $response['message'] = "Wystąpił nieoczekiwany błąd serwera.";
                http_response_code(500);
            }
       } else {
            http_response_code(405);
            $response['message'] = 'Metoda niedozwolona (wymagany POST).';
            api_log("trigger_ai_test_run: Odrzucono żądanie - nieprawidłowa metoda HTTP (wymagany POST).");
       }
        break;

    case 'get_ai_prompt_configs':
        try {
            if (!$pdo) { throw new Exception("Brak połączenia z bazą danych dla get_ai_prompt_configs."); }
            $stmt = $pdo->query("SELECT config_id, system_prompt, ollama_model_name, ollama_temperature, ollama_num_predict, ollama_top_p, description FROM ai_prompt_configs");
            $configs = $stmt->fetchAll(PDO::FETCH_ASSOC);
            $response = ['success' => true, 'configs' => $configs];
        } catch (PDOException $e) {
            error_log("Błąd DB w get_ai_prompt_configs: " . $e->getMessage());
            api_log("Błąd DB w get_ai_prompt_configs: " . $e->getMessage());
            $response['message'] = "Błąd bazy danych przy pobieraniu konfiguracji AI: " . $e->getMessage();
            http_response_code(500);
        } catch (Exception $e) {
            error_log("Ogólny błąd w get_ai_prompt_configs: " . $e->getMessage());
            api_log("Ogólny błąd w get_ai_prompt_configs: " . $e->getMessage());
            $response['message'] = "Błąd serwera przy pobieraniu konfiguracji AI: " . $e->getMessage();
            http_response_code(500);
        }
        break;

    case 'save_ai_prompt_config':
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
            $config_data_save = json_decode($raw_post_data, true); 
            
            $config_id_save = $config_data_save['config_id'] ?? null; 
            $system_prompt_save = $config_data_save['system_prompt'] ?? null; 

            if (!$config_id_save || $system_prompt_save === null) {
                http_response_code(400);
                $response['message'] = 'Nie podano ID konfiguracji lub treści promptu.';
                break;
            }
            $model_name_save = !empty($config_data_save['ollama_model_name']) ? $config_data_save['ollama_model_name'] : null;
            $temp_save = isset($config_data_save['ollama_temperature']) ? (float)$config_data_save['ollama_temperature'] : 0.2;
            $num_pred_save = isset($config_data_save['ollama_num_predict']) ? (int)$config_data_save['ollama_num_predict'] : 60;
            $top_p_save = isset($config_data_save['ollama_top_p']) ? (float)$config_data_save['ollama_top_p'] : 0.8;
            $desc_save = $config_data_save['description'] ?? '';

            try {
                $sql_save_config = "UPDATE ai_prompt_configs SET 
                                        system_prompt = :system_prompt, 
                                        ollama_model_name = :ollama_model_name,
                                        ollama_temperature = :ollama_temperature,
                                        ollama_num_predict = :ollama_num_predict,
                                        ollama_top_p = :ollama_top_p,
                                        description = :description
                                    WHERE config_id = :config_id"; 
                $stmt_save_config = $pdo->prepare($sql_save_config); 
                $stmt_save_config->execute([
                    ':system_prompt' => $system_prompt_save,
                    ':ollama_model_name' => $model_name_save,
                    ':ollama_temperature' => $temp_save,
                    ':ollama_num_predict' => $num_pred_save,
                    ':ollama_top_p' => $top_p_save,
                    ':description' => $desc_save,
                    ':config_id' => $config_id_save
                ]);
                if ($stmt_save_config->rowCount() > 0) {
                    $response = ['success' => true, 'message' => "Konfiguracja AI '$config_id_save' została zaktualizowana."];
                } else {
                    $check_stmt_save_config = $pdo->prepare("SELECT COUNT(*) FROM ai_prompt_configs WHERE config_id = :config_id"); 
                    $check_stmt_save_config->execute([':config_id' => $config_id_save]);
                    if ($check_stmt_save_config->fetchColumn() > 0) {
                        $response = ['success' => true, 'message' => "Konfiguracja AI '$config_id_save' nie wymagała aktualizacji (brak zmian)."];
                    } else {
                        $response['message'] = "Konfiguracja AI '$config_id_save' nie została znaleziona (nie utworzono nowej).";
                         http_response_code(404); 
                    }
                }
            } catch (PDOException $e) {
                error_log("Błąd DB w save_ai_prompt_config: " . $e->getMessage());
                api_log("Błąd DB w save_ai_prompt_config: " . $e->getMessage());
                $response['message'] = "Błąd bazy danych przy zapisie konfiguracji AI: " . $e->getMessage();
                http_response_code(500);
            }
        } else {
            http_response_code(405);
            $response['message'] = 'Metoda niedozwolona (wymagany POST).';
        }
        break;
        
    case 'get_global_ai_settings':
        $python_config = get_python_config();
        if ($python_config && isset($python_config['ai_settings'])) {
            $response = ['success' => true, 'settings' => $python_config['ai_settings']];
        } else {
            $response['message'] = "Nie udało się odczytać globalnych ustawień AI z pliku config.json.";
            http_response_code(500);
        }
        break;

    case 'save_global_ai_settings':
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            $new_settings_data = json_decode($raw_post_data, true);
            if (json_last_error() !== JSON_ERROR_NONE || !is_array($new_settings_data)) {
                $response['message'] = "Nieprawidłowy format danych JSON.";
                http_response_code(400);
                break;
            }

            $config_path = __DIR__ . '/config.json';
            if (!is_writable($config_path)) {
                 $response['message'] = "Błąd uprawnień: Plik config.json nie jest zapisywalny przez serwer.";
                 http_response_code(500);
                 break;
            }

            $current_full_config = get_python_config();
            if (!$current_full_config) {
                $response['message'] = "Nie udało się odczytać istniejącego pliku config.json.";
                http_response_code(500);
                break;
            }
            
            if (isset($new_settings_data['api_base_url']) && isset($current_full_config['ai_settings']['api_base_url'])) {
                $current_full_config['ai_settings']['api_base_url']['value'] = trim($new_settings_data['api_base_url']);
            }
            if (isset($new_settings_data['default_model_name']) && isset($current_full_config['ai_settings']['default_model_name'])) {
                $current_full_config['ai_settings']['default_model_name']['value'] = trim($new_settings_data['default_model_name']);
            }

            $new_json_content = json_encode($current_full_config, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
            
            if (file_put_contents($config_path, $new_json_content) !== false) {
                $response = ['success' => true, 'message' => 'Globalne ustawienia AI zostały zaktualizowane.'];
            } else {
                $response['message'] = "Nie udało się zapisać zmian do pliku config.json.";
                http_response_code(500);
            }
        } else {
            http_response_code(405);
            $response['message'] = 'Metoda niedozwolona (wymagany POST).';
        }
        break;
    
    case 'promote_test_to_production':
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
            try {
                $stmt_get_test_config = $pdo->prepare("SELECT * FROM ai_prompt_configs WHERE config_id = 'test'"); 
                $stmt_get_test_config->execute();
                $test_config_data = $stmt_get_test_config->fetch(PDO::FETCH_ASSOC); 

                if ($test_config_data) {
                    $sql_prod_update_from_test = "UPDATE ai_prompt_configs SET 
                                                    system_prompt = :system_prompt, 
                                                    ollama_model_name = :ollama_model_name,
                                                    ollama_temperature = :ollama_temperature,
                                                    ollama_num_predict = :ollama_num_predict,
                                                    ollama_top_p = :ollama_top_p,
                                                    description = :description 
                                                WHERE config_id = 'production'"; 
                    $stmt_prod_update = $pdo->prepare($sql_prod_update_from_test); 
                    $stmt_prod_update->execute([
                        ':system_prompt' => $test_config_data['system_prompt'],
                        ':ollama_model_name' => $test_config_data['ollama_model_name'],
                        ':ollama_temperature' => $test_config_data['ollama_temperature'],
                        ':ollama_num_predict' => $test_config_data['ollama_num_predict'],
                        ':ollama_top_p' => $test_config_data['ollama_top_p'],
                        ':description' => $test_config_data['description'] . " (Promoted from test " . date("Y-m-d H:i:s") . ")"
                    ]);
                    $response = ['success' => true, 'message' => 'Konfiguracja testowa została przeniesiona do produkcji.'];
                } else {
                    $response['message'] = 'Nie znaleziono konfiguracji testowej do promocji.';
                    http_response_code(404); 
                }
            } catch (PDOException $e) {
                error_log("Błąd DB w promote_test_to_production: " . $e->getMessage());
                api_log("Błąd DB w promote_test_to_production: " . $e->getMessage());
                $response['message'] = "Błąd bazy danych: " . $e->getMessage();
                http_response_code(500);
            }
        } else {
            http_response_code(405);
            $response['message'] = 'Metoda niedozwolona (wymagany POST).';
        }
        break;

    case 'mark_gallery_completed':
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
            $data_mark_completed = json_decode($raw_post_data, true); 
            $gallery_id_mark = $data_mark_completed['gallery_id'] ?? null; 

            if (!$gallery_id_mark) {
                http_response_code(400); $response['message'] = 'Nie podano ID galerii.'; break;
            }

            try {
                $stmt_get_counts_mark = $pdo->prepare("SELECT expected_count, status FROM galleries WHERE gallery_id = :gallery_id"); 
                $stmt_get_counts_mark->execute([':gallery_id' => $gallery_id_mark]);
                $gallery_counts_mark = $stmt_get_counts_mark->fetch(PDO::FETCH_ASSOC); 

                if (!$gallery_counts_mark) {
                    http_response_code(404);
                    $response['message'] = "Nie znaleziono galerii o ID: " . htmlspecialchars($gallery_id_mark);
                    break;
                }

                if ($gallery_counts_mark['status'] === 'completed') {
                     $response = ['success' => true, 'message' => "Galeria '$gallery_id_mark' była już oznaczona jako ukończona."];
                     break;
                }

                $pdo->beginTransaction();
                $sql_update_mark = "UPDATE galleries SET status = 'completed'"; 
                $params_update_mark = [':gallery_id' => $gallery_id_mark]; 
                if ($gallery_counts_mark['expected_count'] !== null) {
                    $sql_update_mark .= ", downloaded_count = expected_count";
                }
                $sql_update_mark .= " WHERE gallery_id = :gallery_id";
                
                $stmt_update_mark_final = $pdo->prepare($sql_update_mark); 
                $stmt_update_mark_final->execute($params_update_mark);

                if ($stmt_update_mark_final->rowCount() > 0) {
                    $pdo->commit();
                    $response = ['success' => true, 'message' => "Galeria '$gallery_id_mark' została oznaczona jako ukończona."];
                    api_log("Galeria '$gallery_id_mark' oznaczona jako ukończona przez użytkownika via API.");
                    clear_models_cache();
                } else {
                    $pdo->rollBack();
                    $response['message'] = "Nie udało się zaktualizować statusu galerii '$gallery_id_mark'.";
                }
            } catch (PDOException $e) {
                if ($pdo->inTransaction()) $pdo->rollBack();
                error_log("Błąd DB w mark_gallery_completed dla ID '$gallery_id_mark': " . $e->getMessage());
                api_log("Błąd DB w mark_gallery_completed dla ID '$gallery_id_mark': " . $e->getMessage());
                $response['message'] = "Błąd bazy danych.";
                http_response_code(500);
            }
        } else {
            http_response_code(405);
            $response['message'] = 'Metoda niedozwolona (wymagany POST).';
        }
        break;

    case 'toggle_gallery_disabled_status':
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
            $data = json_decode($raw_post_data, true);
            $gallery_id = $data['gallery_id'] ?? null;

            if (!$gallery_id) {
                http_response_code(400); $response['message'] = 'Nie podano ID galerii.'; break;
            }

            try {
                $pdo->beginTransaction();
                $stmt_get = $pdo->prepare("SELECT is_disabled FROM galleries WHERE gallery_id = :id FOR UPDATE");
                $stmt_get->execute([':id' => $gallery_id]);
                $current_state = $stmt_get->fetchColumn();

                if ($current_state === false) {
                    $pdo->rollBack();
                    http_response_code(404);
                    $response['message'] = 'Nie znaleziono galerii o podanym ID.';
                    break;
                }

                $new_state = !$current_state;
                $new_status = $new_state ? 'disabled_bad_links' : 'pending_check';

                $stmt_update = $pdo->prepare("UPDATE galleries SET is_disabled = :is_disabled, status = :status WHERE gallery_id = :id");
                $stmt_update->execute([
                    ':is_disabled' => (int)$new_state,
                    ':status' => $new_status,
                    ':id' => $gallery_id
                ]);

                $pdo->commit();
                $response = [
                    'success' => true,
                    'message' => 'Status galerii został zaktualizowany.',
                    'new_state_is_disabled' => $new_state
                ];
                clear_models_cache();

            } catch (PDOException $e) {
                if ($pdo->inTransaction()) $pdo->rollBack();
                error_log("Błąd DB w toggle_gallery_disabled_status: " . $e->getMessage());
                api_log("Błąd DB w toggle_gallery_disabled_status: " . $e->getMessage());
                $response['message'] = 'Błąd bazy danych.';
                http_response_code(500);
            }
        } else {
            http_response_code(405);
            $response['message'] = 'Metoda niedozwolona (wymagany POST).';
        }
        break;

    default:
        http_response_code(400);
        if(isset($action) && !empty($action)){ 
            $response['message'] = "Nieznana akcja: '" . htmlspecialchars($action) . "'.";
            api_log("Nieznana akcja: '" . htmlspecialchars($action) . "'.");
        } else {
            api_log("Brak akcji w żądaniu (lub akcja NULL)."); 
        }
        break;
}

if (!headers_sent()) { 
    echo json_encode($response);
}
exit();
?>