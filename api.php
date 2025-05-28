<?php
// api.php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *'); // Dla dewelopmentu, w produkcji zawęź
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

require_once 'php_config.php'; // Zawiera php_db_config.php
require_once 'php_utils.php';  // Zawiera funkcje pomocnicze i DB

if ($_SERVER['REQUEST_METHOD'] == 'OPTIONS') {
    http_response_code(200);
    exit();
}

$action = $_GET['action'] ?? $_POST['action'] ?? null;
$response = ['success' => false, 'message' => 'Nieznana akcja lub brak akcji.'];
$pdo = get_db_connection(); // Próbuj nawiązać połączenie na początku

// Sprawdzenie połączenia PDO jest teraz bardziej ogólne
if (!$pdo && !in_array($action, ['get_status'])) { // get_status może próbować działać bez DB dla początkowego komunikatu
    http_response_code(503); // Service Unavailable
    $response['message'] = 'Błąd serwera: Nie można połączyć się z bazą danych.';
    echo json_encode($response);
    exit();
}


switch ($action) {
    case 'get_status':
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
        $queue_data = get_priority_queue_db(); 
        echo json_encode($queue_data); 
        exit();

    case 'get_aggregate':
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
            
            if (empty($models_from_db)) {
                $models_in_list_txt = read_model_list_from_file();
                foreach ($models_in_list_txt as $model_name_from_list) {
                    if (!isset($aggregate_data['models'][$model_name_from_list])) {
                        $sanitized_from_list = sanitize_foldername($model_name_from_list);
                        $aggregate_data['models'][$model_name_from_list] = [
                            'galleries' => [],
                            'sanitized_name' => $sanitized_from_list,
                            'total_galleries' => 0,
                            'completed_galleries' => 0,
                            'model_progress' => 0
                        ];
                    }
                }
            }

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
                    error_log("Ostrzeżenie (get_aggregate): Galeria ".$gallery_row['gallery_id']." ma model_id ".$gallery_row['model_id'].", który nie był w początkowej liście modeli. Dodano model: " . $model_name_for_gallery);
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
                    'folder' => $gallery_row['folder_path'], // Pełna ścieżka systemowa
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
            
            // Wyodrębnienie nazwy folderu galerii ze ścieżki absolutnej
            // Przykład: D:\...\Modelki\ModelSanitizedName\GalleryFolder_ID -> GalleryFolder_ID
            $gallery_folder_name_only = basename($absolute_folder_path);

            // Tworzenie ścieżki względnej dla URL
            // Zakładamy, że BASE_DATA_DIR_NAME ("Modelki") jest bezpośrednio w web root projektu
            $web_path_segment = BASE_DATA_DIR_NAME . '/' . $model_sanitized_name . '/' . $gallery_folder_name_only;


            if (!is_dir($absolute_folder_path)) {
                $response['message'] = "Folder galerii nie istnieje na serwerze: " . htmlspecialchars($absolute_folder_path);
                $response['files'] = [];
                $response['web_path_segment'] = $web_path_segment; // Mimo wszystko zwróć ścieżkę, może się przydać
                $response['success'] = true; // Sukces, bo znaleźliśmy dane galerii, ale folder jest pusty/nie istnieje
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
            // Sortuj pliki alfanumerycznie dla spójnej kolejności
            natsort($files); 
            $response = [
                'success' => true,
                'files' => array_values($files), // array_values do zresetowania kluczy po natsort
                'web_path_segment' => $web_path_segment, // np. Modelki/ModelName/GalleryFolder_ID
                'gallery_id' => $gallery_id // Dodajemy ID galerii do odpowiedzi dla JS
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

    case 'add_model':
        $model_name_param = trim($_GET['model_name'] ?? '');
        if (!empty($model_name_param)) {
            $current_list_from_file = read_model_list_from_file();
            $exists_in_file = false;
            foreach ($current_list_from_file as $m) {
                if (strcasecmp($m, $model_name_param) === 0) { $exists_in_file = true; break; }
            }

            if ($exists_in_file) {
                $response['message'] = "Modelka '$model_name_param' już istnieje na liście w pliku lista.txt.";
            } else {
                $file_handle = fopen(LIST_FILE_PATH, 'a+'); 
                if ($file_handle) {
                    if (flock($file_handle, LOCK_EX)) { 
                        fseek($file_handle, 0, SEEK_END); 
                        $current_size = ftell($file_handle);
                        $line_to_add = $model_name_param . "\n";

                        if ($current_size > 0) {
                            fseek($file_handle, -1, SEEK_END); 
                            if (fread($file_handle, 1) !== "\n") {
                                $line_to_add = "\n" . $line_to_add; 
                            }
                        }
                        fwrite($file_handle, $line_to_add);
                        fflush($file_handle); 
                        flock($file_handle, LOCK_UN); 
                        $response = ['success' => true, 'message' => "Modelka '$model_name_param' dodana do lista.txt."];
                    } else {
                        $response['message'] = "Nie udało się uzyskać blokady na pliku lista.txt.";
                    }
                    fclose($file_handle);
                } else {
                    $response['message'] = "Błąd otwarcia pliku lista.txt.";
                }
            }
        } else {
            $response['message'] = "Nie podano nazwy modelki.";
        }
        break;

    case 'prioritize':
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

    default:
        http_response_code(400);
        $response['message'] = "Nieznana akcja: '$action'.";
        break;
}

echo json_encode($response);
?>