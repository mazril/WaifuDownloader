<?php
// Extracted from api.php case 'trigger_ai_update'
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
