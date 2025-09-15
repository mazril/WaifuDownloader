<?php
// Extracted from api.php case 'toggle_gallery_disabled_status'
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
            $data = json_decode($raw_post_data, true);
            $gallery_id = $data['gallery_id'] ?? null;

            if (!$gallery_id) {
                http_response_code(400); $response['message'] = 'Nie podano ID galerii.'; break;
            }

            try {
                $pdo->beginTransaction();
                $stmt_get = $pdo->prepare("SELECT is_disabled FROM galleries WHERE gallery_id = :id FOR UPDATE");
                $stmt_get->execute([':id' => $gallery_id]);
                $current_state = $stmt_get->fetchColumn();

                if ($current_state === false) {
                    $pdo->rollBack();
                    http_response_code(404);
                    $response['message'] = 'Nie znaleziono galerii o podanym ID.';
                    break;
                }

                $new_state = !$current_state;
                $new_status = $new_state ? 'disabled_bad_links' : 'pending_check';

                $stmt_update = $pdo->prepare("UPDATE galleries SET is_disabled = :is_disabled, status = :status WHERE gallery_id = :id");
                $stmt_update->execute([
                    ':is_disabled' => (int)$new_state,
                    ':status' => $new_status,
                    ':id' => $gallery_id
                ]);

                $pdo->commit();
                $response = [
                    'success' => true,
                    'message' => 'Status galerii został zaktualizowany.',
                    'new_state_is_disabled' => $new_state
                ];
                clear_models_cache();

            } catch (PDOException $e) {
                if ($pdo->inTransaction()) $pdo->rollBack();
                error_log("Błąd DB w toggle_gallery_disabled_status: " . $e->getMessage());
                api_log("Błąd DB w toggle_gallery_disabled_status: " . $e->getMessage());
                $response['message'] = 'Błąd bazy danych.';
                http_response_code(500);
            }
        } else {
            http_response_code(405);
            $response['message'] = 'Metoda niedozwolona (wymagany POST).';
        }
        break;

    default:
        http_response_code(400);
        if(isset($action) && !empty($action)){ 
            $response['message'] = "Nieznana akcja: '" . htmlspecialchars($action) . "'.";
            api_log("Nieznana akcja: '" . htmlspecialchars($action) . "'.");
        } else {
            api_log("Brak akcji w żądaniu (lub akcja NULL)."); 
        }
