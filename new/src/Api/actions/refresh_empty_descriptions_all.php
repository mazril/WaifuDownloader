<?php
// Extracted from api.php case 'refresh_empty_descriptions_all'
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
