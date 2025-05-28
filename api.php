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
$pdo = get_db_connection();

if (!$pdo && !in_array($action, ['get_status'])) { // get_status może próbować działać bez DB dla początkowego komunikatu
    http_response_code(503); // Service Unavailable
    $response['message'] = 'Błąd serwera: Nie można połączyć się z bazą danych.';
    echo json_encode($response);
    exit();
}


switch ($action) {
    case 'get_status':
        $status_data = get_app_state_db('current_status'); // Pobierz z DB
        if ($status_data && is_array($status_data)) {
            // Upewnij się, że wszystkie kluczowe pola istnieją
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
        $queue_data = get_priority_queue_db(); // Pobierz z DB
        echo json_encode($queue_data); // Zawsze zwracaj tablicę, nawet pustą
        exit();

    case 'get_aggregate':
        // Ta funkcja będzie teraz budować agregat na podstawie danych z tabel models i galleries
        $aggregate_data = ['models' => []];
        try {
            // 1. Pobierz wszystkie modelki
            $stmt_models = $pdo->query("SELECT model_id, model_name, sanitized_name FROM models ORDER BY model_name ASC");
            $models_from_db = $stmt_models->fetchAll(PDO::FETCH_ASSOC);

            if (empty($models_from_db)) {
                 // Sprawdź, czy są modelki w lista.txt, aby zapewnić puste wpisy, jeśli DB jest pusta, ale lista.txt nie
                $models_in_list_txt = read_model_list_from_file();
                foreach ($models_in_list_txt as $model_name_from_list) {
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


            $stmt_galleries = $pdo->prepare("
                SELECT gallery_id, url, original_title, determined_title, folder_path,
                       expected_count, downloaded_count, status
                FROM galleries
                WHERE model_id = :model_id
                ORDER BY COALESCE(determined_title, original_title, gallery_id) ASC
            ");

            foreach ($models_from_db as $model_row) {
                $model_name_original = $model_row['model_name'];
                $sanitized_name = $model_row['sanitized_name'];
                $model_id = $model_row['model_id'];

                $aggregate_data['models'][$model_name_original] = [
                    'galleries' => [],
                    'sanitized_name' => $sanitized_name,
                    'total_galleries' => 0,
                    'completed_galleries' => 0,
                    'model_progress' => 0
                ];

                $stmt_galleries->execute([':model_id' => $model_id]);
                $galleries_for_model = $stmt_galleries->fetchAll(PDO::FETCH_ASSOC);

                $completed_count_for_model = 0;
                foreach ($galleries_for_model as $gallery_row) {
                    $is_complete_status = in_array($gallery_row['status'], ["completed", "completed_with_tolerance"]);
                    if ($is_complete_status) {
                        $completed_count_for_model++;
                    }
                    $expected = $gallery_row['expected_count'];
                    $downloaded = $gallery_row['downloaded_count'];
                    $status_color = $is_complete_status ? 'green' : ($downloaded > 0 ? 'orange' : 'red');

                    $aggregate_data['models'][$model_name_original]['galleries'][$gallery_row['gallery_id']] = [
                        'title' => $gallery_row['determined_title'] ?: $gallery_row['original_title'] ?: $gallery_row['gallery_id'],
                        'folder' => $gallery_row['folder_path'],
                        'expected' => $expected,
                        'downloaded' => $downloaded,
                        'url' => $gallery_row['url'],
                        'status_color' => $status_color,
                        'completed' => $is_complete_status,
                        'model_name' => $model_name_original, // Dla spójności z JS
                        'gallery_id' => $gallery_row['gallery_id'] // Dla spójności z JS
                    ];
                }
                $total_galleries_for_model = count($galleries_for_model);
                $aggregate_data['models'][$model_name_original]['total_galleries'] = $total_galleries_for_model;
                $aggregate_data['models'][$model_name_original]['completed_galleries'] = $completed_count_for_model;
                $aggregate_data['models'][$model_name_original]['model_progress'] = ($total_galleries_for_model > 0) ? ($completed_count_for_model / $total_galleries_for_model * 100) : 0;
            }

        } catch (PDOException $e) {
            error_log("Błąd DB w get_aggregate: " . $e->getMessage());
            $response['message'] = 'Błąd pobierania danych agregatu z bazy.';
            echo json_encode($response); // Zwróć błąd i zakończ
            exit();
        }
        echo json_encode($aggregate_data);
        exit();

    case 'update_queue':
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            $post_data = file_get_contents('php://input');
            $new_queue_from_js = json_decode($post_data, true);

            if (is_array($new_queue_from_js)) {
                if (update_priority_queue_db($new_queue_from_js)) { // Zapisz do DB
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
            // Najpierw dodaj/zaktualizuj w bazie danych (Python i tak to zrobi, ale możemy tu też)
            // Tutaj tylko dodajemy do lista.txt, Python zsynchronizuje z bazą `models` przy przetwarzaniu.
            $current_list_from_file = read_model_list_from_file();
            $exists_in_file = false;
            foreach ($current_list_from_file as $m) {
                if (strcasecmp($m, $model_name_param) === 0) { $exists_in_file = true; break; }
            }

            if ($exists_in_file) {
                $response['message'] = "Modelka '$model_name_param' już istnieje na liście w pliku lista.txt.";
            } else {
                // Dodawanie do pliku lista.txt (jak poprzednio)
                $file_handle = fopen(LIST_FILE_PATH, 'a+'); // a+ otwiera do odczytu i zapisu; wskaźnik na końcu
                if ($file_handle) {
                    if (flock($file_handle, LOCK_EX)) { // Zablokuj plik
                        // Sprawdź, czy ostatnia linia to newline
                        fseek($file_handle, 0, SEEK_END); // Idź na koniec
                        $current_size = ftell($file_handle);
                        $line_to_add = $model_name_param . "\n";

                        if ($current_size > 0) {
                            fseek($file_handle, -1, SEEK_END); // Cofnij o 1 bajt
                            if (fread($file_handle, 1) !== "\n") {
                                $line_to_add = "\n" . $line_to_add; // Dodaj newline, jeśli go nie ma
                            }
                        }
                        fwrite($file_handle, $line_to_add);
                        fflush($file_handle); // Upewnij się, że dane są zapisane
                        flock($file_handle, LOCK_UN); // Odblokuj plik
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
        $id_param = $_GET['id'] ?? null; // Dla 'scan_model' to nazwa modelki, dla 'gallery' to ID galerii

        if ($type_param && $id_param) {
            $item_data_for_queue = null;
            $message = '';
            $added_successfully = false;

            if ($type_param === 'scan_model' || $type_param === 'scan_model_refresh_only') {
                // Dla scan_model, $id_param to nazwa modelki (string)
                $item_data_for_queue = $id_param;
                if (add_to_priority_queue_db($type_param, $item_data_for_queue, true)) {
                    $action_desc = ($type_param === 'scan_model_refresh_only') ? "odświeżania opisów" : "skanowania";
                    $message = "Zadanie $action_desc dla '$id_param' dodane na początek kolejki.";
                    $added_successfully = true;
                } else {
                   $message = "Zadanie dla '$id_param' już jest w kolejce lub wystąpił błąd dodawania do DB.";
                }
            } elseif ($type_param === 'gallery') {
                // Dla gallery, $id_param to ID galerii. Potrzebujemy pobrać resztę danych.
                $gallery_full_data_from_db = find_gallery_data_by_id_db($id_param);
                if ($gallery_full_data_from_db) {
                    // Struktura $item_data dla galerii powinna być słownikiem
                    // zawierającym 'id', 'model_name', 'title', 'count' (opcjonalnie 'url')
                    $item_data_for_queue = [
                        'id' => $gallery_full_data_from_db['id'],
                        'model_name' => $gallery_full_data_from_db['model_name'],
                        'title' => $gallery_full_data_from_db['title'],
                        'count' => $gallery_full_data_from_db['count'] ?? null,
                        // 'url' => $gallery_full_data_from_db['url'] // Można dodać, jeśli potrzebne w Pythonie
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