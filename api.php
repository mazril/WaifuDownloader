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

switch ($action) {
    case 'get_status':
        $status_data = load_json_file(CURRENT_STATUS_FILE_PATH, null);
        if ($status_data) {
            echo json_encode($status_data);
        } else {
            echo json_encode([
                "timestamp" => date("Y-m-d H:i:s"),
                "message" => "Oczekiwanie na pierwszy status ze skryptu Python...",
                "current_model" => "",
                "current_gallery_title" => "",
                "current_gallery_id" => null,
                "current_download_count" => null,
                "scan_session_found_count" => null,
                "current_expected_count" => null,
                "is_processing" => false
            ]);
        }
        exit();

    case 'get_queue':
        $queue_data = load_json_file(PRIORITY_QUEUE_FILE_PATH, []);
        echo json_encode($queue_data);
        exit();

    case 'get_aggregate':
        $aggregate_data = load_json_file(STATUS_JSON_AGGREGATE_PATH, ["models" => []]);
        echo json_encode($aggregate_data);
        exit();

    case 'update_queue':
        if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            $post_data = file_get_contents('php://input');
            $new_queue = json_decode($post_data, true);
            if (is_array($new_queue)) {
                if (save_json_file(PRIORITY_QUEUE_FILE_PATH, $new_queue)) {
                    $response = ['success' => true, 'message' => 'Kolejka zaktualizowana.'];
                } else {
                    $response['message'] = 'Błąd zapisu kolejki do pliku.';
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
        $model_name = trim($_GET['model_name'] ?? '');
        if (!empty($model_name)) {
            $current_list = read_model_list();
            $exists = false;
            foreach ($current_list as $m) {
                if (strcasecmp($m, $model_name) === 0) { $exists = true; break; }
            }
            if ($exists) {
                $response['message'] = "Modelka '$model_name' już istnieje na liście.";
            } else {
                $file_handle = fopen(LIST_FILE_PATH, 'a+');
                if ($file_handle && flock($file_handle, LOCK_EX)) {
                    fseek($file_handle, 0, SEEK_END);
                    $current_size = ftell($file_handle);
                    $line_to_add = $model_name . "\n";
                    if ($current_size > 0) {
                        fseek($file_handle, -1, SEEK_END);
                        if (fread($file_handle, 1) !== "\n") {
                            $line_to_add = "\n" . $line_to_add;
                        }
                    }
                    fwrite($file_handle, $line_to_add);
                    flock($file_handle, LOCK_UN);
                    fclose($file_handle);
                    $response = ['success' => true, 'message' => "Modelka '$model_name' dodana do lista.txt."];
                } else {
                    $response['message'] = "Błąd otwarcia lub blokady pliku lista.txt.";
                }
            }
        } else {
            $response['message'] = "Nie podano nazwy modelki.";
        }
        break;

    case 'prioritize':
        $type = $_GET['type'] ?? null;
        $id_param = $_GET['id'] ?? null;

        if ($type && $id_param) {
            $item_data_for_queue = null;
            $message = '';
            $added_successfully = false;

            if ($type === 'scan_model') {
                $item_data_for_queue = $id_param;
                if (add_to_priority_queue('scan_model', $item_data_for_queue, true)) {
                    $message = "Zadanie skanowania dla '$id_param' dodane na początek kolejki.";
                    $added_successfully = true;
                } else {
                   $message = "Zadanie skanowania dla '$id_param' już jest w kolejce lub wystąpił błąd.";
                }
            } elseif ($type === 'scan_model_refresh_only') { // <-- NOWA SEKCJA
                $item_data_for_queue = $id_param;
                if (add_to_priority_queue('scan_model_refresh_only', $item_data_for_queue, true)) {
                    $message = "Zadanie odświeżania opisów dla '$id_param' dodane na początek kolejki.";
                    $added_successfully = true;
                } else {
                   $message = "Zadanie odświeżania dla '$id_param' już jest w kolejce lub wystąpił błąd.";
                }
            } elseif ($type === 'gallery') {
                $gallery_full_data = find_gallery_data_by_id($id_param);
                if ($gallery_full_data) {
                    $item_data_for_queue = $gallery_full_data;
                    if (add_to_priority_queue('gallery', $item_data_for_queue, true)) {
                        $message = "Galeria '{$gallery_full_data['title']}' (model: {$gallery_full_data['model_name']}) dodana na początek kolejki.";
                        $added_successfully = true;
                    } else {
                        $message = "Galeria '{$gallery_full_data['title']}' już jest w kolejce lub wystąpił błąd.";
                    }
                } else {
                    $message = "Nie znaleziono danych dla galerii o ID '$id_param'.";
                }
            } else {
                $message = "Nieznany typ '$type' do priorytetyzacji.";
            }
            $response = ['success' => $added_successfully, 'message' => $message];
        } else {
            $response['message'] = "Nie podano typu lub ID do priorytetyzacji.";
        }
        break;
}

echo json_encode($response);
?>