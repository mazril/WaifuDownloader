<?php
// Extracted from api.php case 'prioritize'
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
