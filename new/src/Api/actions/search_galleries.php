<?php
// Extracted from api.php case 'search_galleries'
if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
        $search_term = $_GET['term'] ?? '';
        if (empty($search_term)) {
            $response = ['success' => true, 'galleries' => []]; 
            break;
        }

        $galleries = [];
        try {
            $sql = "SELECT g.gallery_id, g.url, g.original_title, g.determined_title, 
                           g.expected_count, g.downloaded_count, g.status,
                           m.model_name, m.sanitized_name as model_sanitized_name
                     FROM galleries g
                     JOIN models m ON g.model_id = m.model_id
                     WHERE g.original_title LIKE ? 
                       OR g.determined_title LIKE ?
                       OR g.gallery_id LIKE ? 
                       OR m.model_name LIKE ?
                     ORDER BY 
                        m.model_name ASC, 
                        COALESCE(
                           CONVERT(g.determined_title USING utf8mb4), 
                           CONVERT(g.original_title USING utf8mb4), 
                           CONVERT(g.gallery_id USING utf8mb4)
                        ) ASC
                     LIMIT 100"; 

            $stmt = $pdo->prepare($sql);
            $term_param = '%' . $search_term . '%';
            $stmt->execute([$term_param, $term_param, $term_param, $term_param]);
            $results = $stmt->fetchAll(PDO::FETCH_ASSOC);

            foreach ($results as $row) {
                $is_complete_status = in_array($row['status'], ["completed", "completed_with_tolerance"]);
                $galleries[] = [
                    'gallery_id' => $row['gallery_id'],
                    'title' => $row['determined_title'] ?: $row['original_title'] ?: $row['gallery_id'],
                    'url' => $row['url'],
                    'model_name' => $row['model_name'],
                    'model_sanitized_name' => $row['model_sanitized_name'],
                    'expected' => $row['expected_count'],
                    'downloaded' => $row['downloaded_count'],
                    'status_color' => $is_complete_status ? 'green' : ($row['downloaded_count'] > 0 ? 'orange' : 'red'),
                    'completed' => $is_complete_status
                ];
            }
            $response = ['success' => true, 'galleries' => $galleries];

        } catch (PDOException $e) {
            error_log("Błąd DB w search_galleries: " . $e->getMessage());
            api_log("Błąd DB w search_galleries: " . $e->getMessage());
            $response['message'] = "Błąd bazy danych podczas wyszukiwania galerii.";
            http_response_code(500);
        }
