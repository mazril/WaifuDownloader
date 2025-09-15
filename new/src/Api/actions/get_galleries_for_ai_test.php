<?php
// Extracted from api.php case 'get_galleries_for_ai_test'
if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
        $model_filter = $_GET['model'] ?? '';
        $status_filter = $_GET['status_filter'] ?? '';
        $limit = isset($_GET['limit']) ? (int)$_GET['limit'] : 50; 
        $offset = isset($_GET['offset']) ? (int)$_GET['offset'] : 0;
        $sort_by = $_GET['sort_by'] ?? 'model_gallery';
        $sort_order = $_GET['sort_order'] ?? 'ASC';
        if (!in_array(strtoupper($sort_order), ['ASC', 'DESC'])) {
            $sort_order = 'ASC';
        }

        try {
            $base_select_sql = "SELECT g.gallery_id, g.original_title, g.determined_title, g.test_ai_title, g.folder_path, g.status, m.model_name ";
            $base_from_sql = "FROM galleries g JOIN models m ON g.model_id = m.model_id";
            
            $where_clauses = [];
            $execute_params_where = [];

            if (!empty($model_filter)) {
                $where_clauses[] = "m.model_name = :model_filter";
                $execute_params_where[':model_filter'] = $model_filter;
            }
            if (!empty($status_filter)) {
                $where_clauses[] = "g.status = :status_filter";
                $execute_params_where[':status_filter'] = $status_filter;
            }

            $where_sql = "";
            if (!empty($where_clauses)) {
                $where_sql = " WHERE " . implode(" AND ", $where_clauses);
            }

            $count_sql = "SELECT COUNT(*) " . $base_from_sql . $where_sql;
            $stmt_count = $pdo->prepare($count_sql);
            $stmt_count->execute($execute_params_where);
            $total_count = $stmt_count->fetchColumn();

            $order_by_map = [
                'model_gallery' => 'm.model_name ' . $sort_order . ', COALESCE(g.determined_title, g.original_title, g.gallery_id) ' . $sort_order,
                'original_title' => 'g.original_title ' . $sort_order,
                'determined_title' => 'g.determined_title ' . $sort_order,
                'test_ai_title' => 'g.test_ai_title ' . $sort_order,
                'status' => 'g.status ' . $sort_order
            ];
            $order_by_clause = $order_by_map[$sort_by] ?? $order_by_map['model_gallery'];

            $data_sql = $base_select_sql . $base_from_sql . $where_sql
                      . " ORDER BY " . $order_by_clause
                      . " LIMIT :limit OFFSET :offset";

            $stmt = $pdo->prepare($data_sql);
            
            foreach ($execute_params_where as $key => $val) {
               $stmt->bindValue($key, $val);
            }
            $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
            $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);

            $stmt->execute();
            $results = $stmt->fetchAll(PDO::FETCH_ASSOC);
            
            $response = ['success' => true, 'galleries' => $results, 'total' => (int)$total_count];

        } catch (PDOException $e) {
            error_log("Błąd DB w get_galleries_for_ai_test: " . $e->getMessage() . " | SQL: " . ($data_sql ?? "N/A"));
            api_log("Błąd DB w get_galleries_for_ai_test: " . $e->getMessage());
            $response['message'] = "Błąd bazy danych: " . $e->getMessage();
            http_response_code(500);
        }
