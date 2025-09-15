<?php
// Extracted from api.php case 'refresh_all_galleries_lists'
if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
        try {
            // Pobierz modele, które nie mają żadnych galerii w bazie (całkowicie puste modele)
            $stmt_empty_models = $pdo->query("
                SELECT m.model_name
                FROM models m
                LEFT JOIN galleries g ON m.model_id = g.model_id
                GROUP BY m.model_id
                HAVING COUNT(g.gallery_id) = 0
                ORDER BY m.model_name ASC
            ");
            $empty_models = $stmt_empty_models->fetchAll(PDO::FETCH_COLUMN);

            // Pobierz wszystkie pozostałe modele
            $stmt_other_models = $pdo->query("
                SELECT m.model_name
                FROM models m
                LEFT JOIN galleries g ON m.model_id = g.model_id
                GROUP BY m.model_id
                HAVING COUNT(g.gallery_id) > 0
                ORDER BY m.model_name ASC
            ");
            $other_models = $stmt_other_models->fetchAll(PDO::FETCH_COLUMN);
            
            $added_count = 0;
            $skipped_count = 0;

            // Najpierw dodaj puste modele na początek kolejki
            foreach ($empty_models as $model_name) {
                if (add_to_priority_queue_db('scan_model', $model_name, true)) {
                    $added_count++;
                } else {
                    $skipped_count++;
                }
            }

            // Następnie dodaj pozostałe modele (na koniec)
            foreach ($other_models as $model_name) {
                if (add_to_priority_queue_db('scan_model', $model_name, false)) {
                    $added_count++;
                } else {
                    $skipped_count++;
                }
            }

            $message = "Dodano $added_count modeli do kolejki skanowania galerii (najpierw puste, potem istniejące).";
            if($skipped_count > 0) $message .= " Pominięto $skipped_count (prawdopodobnie już w kolejce).";
            $response = ['success' => true, 'message' => $message];
            clear_models_cache(); 

        } catch (PDOException $e) {
            error_log("Błąd DB w refresh_all_galleries_lists: " . $e->getMessage());
            api_log("Błąd DB w refresh_all_galleries_lists: " . $e->getMessage());
            $response['message'] = "Błąd bazy danych podczas dodawania zadań skanowania.";
            http_response_code(500);
        }
