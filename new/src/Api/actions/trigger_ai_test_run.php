<?php
// Extracted from api.php case 'trigger_ai_test_run'
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
