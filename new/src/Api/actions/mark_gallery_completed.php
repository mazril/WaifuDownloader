<?php
// Extracted from api.php case 'mark_gallery_completed'
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
