<?php
// api.php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *'); 
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

require_once 'php_config.php'; 
require_once 'php_utils.php';  

if ($_SERVER['REQUEST_METHOD'] == 'OPTIONS') {
    http_response_code(200);
    exit();
}

$action = $_GET['action'] ?? $_POST['action'] ?? null;
$response = ['success' => false, 'message' => 'Nieznana akcja lub brak akcji.'];
$pdo = get_db_connection(); 

if (!$pdo && !in_array($action, ['get_status'])) { 
    http_response_code(503); 
    $response['message'] = 'Błąd serwera: Nie można połączyć się z bazą danych.';
    echo json_encode($response);
    exit();
}


switch ($action) {
    case 'get_status':
        // ... (bez zmian)
        $status_data = get_app_state_db('current_status'); 
        if ($status_data && is_array($status_data)) {
            $defaults = [
                "timestamp" => date("Y-m-d H:i:s"),
                "message" => "Brak danych statusu.",
                "current_model" => "", "current_gallery_title" => "", "current_gallery_id" => null,
                "current_download_count" => null, "scan_session_found_count" => null,
                "current_expected_count" => null, "is_processing" => false
            ];
            echo json_encode(array_merge($defaults, $status_data));
        } else {
             error_log("API get_status: Nie udało się pobrać statusu z DB lub jest w niepoprawnym formacie.");
            echo json_encode([
                "timestamp" => date("Y-m-d H:i:s"),
                "message" => "Oczekiwanie na pierwszy status ze skryptu Python (DB)...",
                "current_model" => "", "current_gallery_title" => "", "current_gallery_id" => null,
                "current_download_count" => null, "scan_session_found_count" => null,
                "current_expected_count" => null, "is_processing" => false
            ]);
        }
        exit();

    case 'get_queue':
        // ... (bez zmian)
        $queue_data = get_priority_queue_db(); 
        echo json_encode($queue_data); 
        exit();

    case 'get_aggregate':
        // ... (bez zmian, jak w poprzedniej odpowiedzi)
        $aggregate_data = ['models' => []];
        try {
            $stmt_models = $pdo->query("SELECT model_id, model_name, sanitized_name FROM models ORDER BY model_name ASC");
            $models_from_db = $stmt_models->fetchAll(PDO::FETCH_ASSOC);

            $model_map = []; 
            foreach ($models_from_db as $model_row) {
                $model_name_original = $model_row['model_name'];
                $model_map[$model_row['model_id']] = $model_name_original;
                $aggregate_data['models'][$model_name_original] = [
                    'galleries' => [],
                    'sanitized_name' => $model_row['sanitized_name'],
                    'total_galleries' => 0,
                    'completed_galleries' => 0,
                    'model_progress' => 0
                ];
            }
            
            // Ta część nie jest już potrzebna, bo php_utils::read_model_list_from_file() nie jest wywoływane
            // if (empty($models_from_db)) {
            //     $models_in_list_txt = read_model_list_from_file(); // To by odwoływało się do pliku
            //     foreach ($models_in_list_txt as $model_name_from_list) {
            //         // ... logika dodawania pustych modeli
            //     }
            // }

            $all_galleries_stmt = $pdo->query("
                SELECT g.gallery_id, g.model_id, g.url, g.original_title, g.determined_title, 
                       g.folder_path, g.expected_count, g.downloaded_count, g.status,
                       m.model_name AS model_name_from_join, m.sanitized_name AS model_sanitized_name_from_join
                FROM galleries g
                JOIN models m ON g.model_id = m.model_id
                ORDER BY m.model_name ASC, COALESCE(g.determined_title, g.original_title, g.gallery_id) ASC
            ");
            $all_galleries = $all_galleries_stmt->fetchAll(PDO::FETCH_ASSOC);

            foreach ($all_galleries as $gallery_row) {
                $model_name_for_gallery = $gallery_row['model_name_from_join'];

                if (!isset($aggregate_data['models'][$model_name_for_gallery])) {
                    $sani_name = $gallery_row['model_sanitized_name_from_join'] ?: sanitize_foldername($model_name_for_gallery);
                    $aggregate_data['models'][$model_name_for_gallery] = [
                        'galleries' => [],
                        'sanitized_name' => $sani_name,
                        'total_galleries' => 0,
                        'completed_galleries' => 0,
                        'model_progress' => 0
                    ];
                }

                $is_complete_status = in_array($gallery_row['status'], ["completed", "completed_with_tolerance"]);
                if ($is_complete_status) {
                    $aggregate_data['models'][$model_name_for_gallery]['completed_galleries']++;
                }
                $aggregate_data['models'][$model_name_for_gallery]['total_galleries']++;

                $expected = $gallery_row['expected_count'];
                $downloaded = $gallery_row['downloaded_count'];
                $status_color = $is_complete_status ? 'green' : ($downloaded > 0 ? 'orange' : 'red');

                $aggregate_data['models'][$model_name_for_gallery]['galleries'][$gallery_row['gallery_id']] = [
                    'title' => $gallery_row['determined_title'] ?: $gallery_row['original_title'] ?: $gallery_row['gallery_id'],
                    'folder' => $gallery_row['folder_path'], 
                    'expected' => $expected,
                    'downloaded' => $downloaded,
                    'url' => $gallery_row['url'],
                    'status_color' => $status_color,
                    'completed' => $is_complete_status,
                    'model_name' => $model_name_for_gallery,
                    'gallery_id' => $gallery_row['gallery_id']
                ];
            }

            foreach ($aggregate_data['models'] as $model_name_key => &$model_data_ref) { 
                if ($model_data_ref['total_galleries'] > 0) {
                    $model_data_ref['model_progress'] = ($model_data_ref['completed_galleries'] / $model_data_ref['total_galleries'] * 100);
                } else {
                    $model_data_ref['model_progress'] = 0;
                }
            }
            unset($model_data_ref); 

        } catch (PDOException $e) {
            error_log("Błąd DB w get_aggregate: " . $e->getMessage());
            $response['message'] = 'Błąd pobierania danych agregatu z bazy.';
            echo json_encode($response); 
            exit();
        }
        echo json_encode($aggregate_data);
        exit();

    case 'get_gallery_files':
        // ... (bez zmian, jak w poprzedniej odpowiedzi)
        $gallery_id = $_GET['gallery_id'] ?? null;
        if (!$gallery_id) {
            $response['message'] = "Nie podano ID galerii.";
            echo json_encode($response);
            exit();
        }
        try {
            $stmt = $pdo->prepare("
                SELECT g.folder_path, m.sanitized_name as model_sanitized_name
                FROM galleries g
                JOIN models m ON g.model_id = m.model_id
                WHERE g.gallery_id = :gallery_id
            ");
            $stmt->execute([':gallery_id' => $gallery_id]);
            $gallery_data = $stmt->fetch(PDO::FETCH_ASSOC);

            if (!$gallery_data || empty($gallery_data['folder_path'])) {
                $response['message'] = "Nie znaleziono ścieżki folderu dla galerii o ID: " . htmlspecialchars($gallery_id) . " lub ścieżka jest pusta.";
                echo json_encode($response);
                exit();
            }
            $absolute_folder_path = $gallery_data['folder_path'];
            $model_sanitized_name = $gallery_data['model_sanitized_name'];
            $gallery_folder_name_only = basename($absolute_folder_path);
            $web_path_segment = BASE_DATA_DIR_NAME . '/' . $model_sanitized_name . '/' . $gallery_folder_name_only;

            if (!is_dir($absolute_folder_path)) {
                $response['message'] = "Folder galerii nie istnieje na serwerze: " . htmlspecialchars($absolute_folder_path);
                $response['files'] = [];
                $response['web_path_segment'] = $web_path_segment; 
                $response['success'] = true; 
                echo json_encode($response);
                exit();
            }
            $allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp'];
            $files = [];
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
            $response = [
                'success' => true,
                'files' => array_values($files), 
                'web_path_segment' => $web_path_segment, 
                'gallery_id' => $gallery_id 
            ];
        } catch (PDOException $e) {
            error_log("Błąd DB w get_gallery_files dla ID '$gallery_id': " . $e->getMessage());
            $response['message'] = "Błąd bazy danych podczas pobierania informacji o galerii.";
        } catch (Exception $e) {
            error_log("Inny błąd w get_gallery_files dla ID '$gallery_id': " . $e->getMessage());
            $response['message'] = "Wystąpił nieoczekiwany błąd serwera.";
        }
        echo json_encode($response);
        exit();


    case 'update_queue':
        // ... (bez zmian)
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            $post_data = file_get_contents('php://input');
            $new_queue_from_js = json_decode($post_data, true);

            if (is_array($new_queue_from_js)) {
                if (update_priority_queue_db($new_queue_from_js)) { 
                    $response = ['success' => true, 'message' => 'Kolejka zaktualizowana w bazie danych.'];
                } else {
                    $response['message'] = 'Błąd zapisu kolejki do bazy danych.';
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

    case 'add_model': // ZMODYFIKOWANO
        $model_name_param = trim($_GET['model_name'] ?? '');
        if (empty($model_name_param)) {
            $response['message'] = "Nie podano nazwy modelki.";
            echo json_encode($response);
            exit();
        }

        try {
            $sanitized_name = sanitize_foldername($model_name_param); // Użyj tej samej funkcji co Python
            
            // Sprawdź, czy modelka już istnieje
            $stmt_check = $pdo->prepare("SELECT model_id FROM models WHERE model_name = :model_name OR sanitized_name = :sanitized_name");
            $stmt_check->execute([':model_name' => $model_name_param, ':sanitized_name' => $sanitized_name]);
            if ($stmt_check->fetch()) {
                $response['message'] = "Modelka '$model_name_param' (lub jej znormalizowana forma) już istnieje w bazie danych.";
            } else {
                // Dodaj nową modelkę
                $stmt_insert = $pdo->prepare("INSERT INTO models (model_name, sanitized_name) VALUES (:model_name, :sanitized_name)");
                $stmt_insert->execute([':model_name' => $model_name_param, ':sanitized_name' => $sanitized_name]);
                if ($stmt_insert->rowCount() > 0) {
                    $response = ['success' => true, 'message' => "Modelka '$model_name_param' dodana do bazy danych."];
                    // Opcjonalnie: można dodać do kolejki zadanie 'scan_model' dla nowo dodanej modelki
                    // add_to_priority_queue_db('scan_model', $model_name_param, true);
                } else {
                    $response['message'] = "Nie udało się dodać modelki '$model_name_param' do bazy danych.";
                }
            }
        } catch (PDOException $e) {
            error_log("Błąd DB w akcji add_model: " . $e->getMessage());
            $response['message'] = "Błąd bazy danych podczas dodawania modelki: " . $e->getMessage();
        }
        break;

    case 'prioritize':
        // ... (bez zmian)
        $type_param = $_GET['type'] ?? null;
        $id_param = $_GET['id'] ?? null; 

        if ($type_param && $id_param) {
            $item_data_for_queue = null;
            $message = '';
            $added_successfully = false;

            if ($type_param === 'scan_model' || $type_param === 'scan_model_refresh_only') {
                $item_data_for_queue = $id_param;
                if (add_to_priority_queue_db($type_param, $item_data_for_queue, true)) {
                    $action_desc = ($type_param === 'scan_model_refresh_only') ? "odświeżania opisów" : "skanowania";
                    $message = "Zadanie $action_desc dla '$id_param' dodane na początek kolejki.";
                    $added_successfully = true;
                } else {
                   $message = "Zadanie dla '$id_param' już jest w kolejce lub wystąpił błąd dodawania do DB.";
                }
            } elseif ($type_param === 'gallery') {
                $gallery_full_data_from_db = find_gallery_data_by_id_db($id_param);
                if ($gallery_full_data_from_db) {
                    $item_data_for_queue = [
                        'id' => $gallery_full_data_from_db['id'],
                        'model_name' => $gallery_full_data_from_db['model_name'],
                        'title' => $gallery_full_data_from_db['title'],
                        'count' => $gallery_full_data_from_db['count'] ?? null,
                    ];
                    if (add_to_priority_queue_db('gallery', $item_data_for_queue, true)) {
                        $message = "Galeria '{$item_data_for_queue['title']}' (model: {$item_data_for_queue['model_name']}) dodana na początek kolejki.";
                        $added_successfully = true;
                    } else {
                        $message = "Galeria '{$item_data_for_queue['title']}' już jest w kolejce lub wystąpił błąd dodawania do DB.";
                    }
                } else {
                    $message = "Nie znaleziono danych dla galerii o ID '$id_param' w bazie danych.";
                }
            } else {
                $message = "Nieznany typ '$type_param' do priorytetyzacji.";
            }
            $response = ['success' => $added_successfully, 'message' => $message];
        } else {
            $response['message'] = "Nie podano typu lub ID do priorytetyzacji.";
        }
        break;
    
    // NOWA AKCJA: search_galleries
    case 'search_galleries':
        $search_term = $_GET['term'] ?? '';
        if (empty($search_term)) {
            $response['galleries'] = [];
            $response['success'] = true; // Zwracamy pustą listę, to nie błąd
            echo json_encode($response);
            exit();
        }

        $galleries = [];
        try {
            $sql = "SELECT g.gallery_id, g.url, g.original_title, g.determined_title, 
                           g.expected_count, g.downloaded_count, g.status,
                           m.model_name, m.sanitized_name as model_sanitized_name
                    FROM galleries g
                    JOIN models m ON g.model_id = m.model_id
                    WHERE g.original_title LIKE :term 
                       OR g.determined_title LIKE :term
                       OR g.gallery_id LIKE :term 
                       OR m.model_name LIKE :term
                    ORDER BY m.model_name ASC, COALESCE(g.determined_title, g.original_title, g.gallery_id) ASC
                    LIMIT 100"; // Limit wyników dla wydajności

            $stmt = $pdo->prepare($sql);
            $stmt->execute([':term' => '%' . $search_term . '%']);
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
            $response['message'] = "Błąd bazy danych podczas wyszukiwania galerii.";
        }
        echo json_encode($response);
        exit();

    // NOWA AKCJA: refresh_empty_descriptions_all
    case 'refresh_empty_descriptions_all':
        $models_to_refresh = [];
        try {
            // Znajdź modelki, które mają przynajmniej jedną galerię z expected_count IS NULL lub 0 i downloaded_count = 0
            // To bardziej złożone zapytanie, aby uniknąć odświeżania modeli, które są faktycznie puste (bez galerii).
            // Lepszym podejściem byłoby, gdyby Python miał flagę "wymaga odświeżenia opisów" na modelu.
            // Na razie, prostsze: znajdź modelki z galeriami 0/0 lub ?/0.
            // LUB, dla uproszczenia, po prostu dodaj *wszystkie* modele do kolejki scan_model_refresh_only.
            // Python i tak pominie te, które nie wymagają aktualizacji.

            $stmt = $pdo->query("SELECT model_name FROM models ORDER BY model_name ASC");
            $all_models = $stmt->fetchAll(PDO::FETCH_COLUMN);
            
            $added_count = 0;
            foreach ($all_models as $model_name) {
                 // Używamy prepend=false, aby nie zakłócać bieżących priorytetów,
                 // a Python i tak przetworzy kolejkę.
                if(add_to_priority_queue_db('scan_model_refresh_only', $model_name, false)) {
                    $added_count++;
                }
            }
            $response = ['success' => true, 'message' => "Dodano $added_count modeli do kolejki odświeżania opisów."];

        } catch (PDOException $e) {
            error_log("Błąd DB w refresh_empty_descriptions_all: " . $e->getMessage());
            $response['message'] = "Błąd bazy danych podczas dodawania zadań odświeżania.";
        }
        echo json_encode($response);
        exit();


    default:
        http_response_code(400);
        $response['message'] = "Nieznana akcja: '$action'.";
        break;
}

echo json_encode($response);
?>