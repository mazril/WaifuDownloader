<?php
// Extracted from api.php case 'rename_gallery_folder'
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
