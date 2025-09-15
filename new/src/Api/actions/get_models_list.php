<?php
// Extracted from api.php case 'get_models_list'
if (file_exists(MODELS_CACHE_FILE) && (time() - filemtime(MODELS_CACHE_FILE) < MODELS_CACHE_TIME)) {
            api_log("Zwracam listę modeli z cache.");
            readfile(MODELS_CACHE_FILE);
            exit();
        }
        api_log("Generuję nową listę modeli (cache nie istnieje lub jest przestarzały).");

        $models_data = [];
        try {
            if (!$pdo) throw new Exception("Brak połączenia z bazą danych dla get_models_list.");

            $sql = "
                SELECT 
                    m.model_id, 
                    m.model_name, 
                    m.sanitized_name,
                    COUNT(g.gallery_id) as total_galleries,
                    SUM(CASE WHEN g.status IN ('completed', 'completed_with_tolerance') THEN 1 ELSE 0 END) as completed_galleries
                FROM models m
                LEFT JOIN galleries g ON m.model_id = g.model_id
                GROUP BY m.model_id, m.model_name, m.sanitized_name
                ORDER BY m.model_name ASC
            ";
            $stmt = $pdo->query($sql);
            $results = $stmt->fetchAll(PDO::FETCH_ASSOC);

            foreach ($results as $row) {
                $total = (int)$row['total_galleries'];
                $completed = (int)$row['completed_galleries'];
                $progress = ($total > 0) ? ($completed / $total * 100) : 0;

                $models_data[] = [
                    'model_name' => $row['model_name'],
                    'sanitized_name' => $row['sanitized_name'],
                    'total_galleries' => $total,
                    'completed_galleries' => $completed,
                    'model_progress' => $progress
                ];
            }
            
            $response = ['success' => true, 'models' => $models_data];

            if (!is_dir(AGGREGATE_CACHE_DIR)) {
                @mkdir(AGGREGATE_CACHE_DIR, 0775, true);
            }
            file_put_contents(MODELS_CACHE_FILE, json_encode($response), LOCK_EX);

        } catch (PDOException $e) {
            error_log("Błąd DB w get_models_list: " . $e->getMessage());
            api_log("Błąd DB w get_models_list: " . $e->getMessage());
            $response['message'] = 'Błąd pobierania listy modeli z bazy.';
            http_response_code(500);
        } catch (Exception $e) {
            error_log("Ogólny błąd w get_models_list: " . $e->getMessage());
            api_log("Ogólny błąd w get_models_list: " . $e->getMessage());
            $response['message'] = 'Błąd serwera przy pobieraniu listy modeli.';
            http_response_code(500);
        }
