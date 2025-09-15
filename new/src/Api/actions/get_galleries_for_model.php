<?php
// Extracted from api.php case 'get_galleries_for_model'
$model_name = $_GET['model_name'] ?? null;
        if (!$model_name) {
            $response['message'] = "Nie podano nazwy modelki.";
            http_response_code(400);
            break;
        }

        $galleries_data = [];
        try {
            if (!$pdo) throw new Exception("Brak połączenia z bazą danych dla get_galleries_for_model.");
            
            $stmt = $pdo->prepare("
                SELECT g.gallery_id, g.url, g.original_title, g.determined_title, 
                       g.folder_path, g.expected_count, g.downloaded_count, g.status, g.is_disabled,
                       m.model_name, m.sanitized_name AS model_sanitized_name
                FROM galleries g
                JOIN models m ON g.model_id = m.model_id
                WHERE m.model_name = :model_name
                ORDER BY COALESCE(g.determined_title, g.original_title, g.gallery_id) ASC
            ");
            $stmt->execute([':model_name' => $model_name]);
            $galleries = $stmt->fetchAll(PDO::FETCH_ASSOC);

            foreach ($galleries as $gallery_row) {
                $is_complete_status = in_array($gallery_row['status'], ["completed", "completed_with_tolerance"]);
                $expected = $gallery_row['expected_count'];
                $downloaded = $gallery_row['downloaded_count'];
                $status_color = $is_complete_status ? 'green' : ($downloaded > 0 ? 'orange' : 'red');
                
                $thumbnails = [];
                $web_path_segment = '';
                if (!empty($gallery_row['folder_path']) && is_dir($gallery_row['folder_path'])) {
                    $model_sanitized_name = $gallery_row['model_sanitized_name'];
                    $gallery_folder_name_only = basename($gallery_row['folder_path']);
                    $web_path_segment = (defined('BASE_DATA_DIR_NAME') ? BASE_DATA_DIR_NAME : "Modelki") . '/' . $model_sanitized_name . '/' . $gallery_folder_name_only;
                    
                    if (is_readable($gallery_row['folder_path'])) {
                        try {
                            $allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp'];
                            $files = [];
                            $dir_iterator = new DirectoryIterator($gallery_row['folder_path']);
                            foreach ($dir_iterator as $fileinfo) {
                                if ($fileinfo->isFile() && in_array(strtolower($fileinfo->getExtension()), $allowed_extensions)) {
                                    $files[] = $fileinfo->getFilename();
                                }
                            }
                            natsort($files);
                            $thumbnails = array_slice(array_values($files), 0, THUMBNAIL_LIMIT);
                        } catch (Exception $e) {
                            api_log("Błąd odczytu katalogu (iterator) dla miniaturek: " . $gallery_row['folder_path'] . " | Błąd: " . $e->getMessage());
                        }
                    } else {
                        api_log("Błąd odczytu katalogu (nieczytelny) dla miniaturek: " . $gallery_row['folder_path']);
                    }
                }

                $galleries_data[$gallery_row['gallery_id']] = [
                    'title' => $gallery_row['determined_title'] ?: $gallery_row['original_title'] ?: $gallery_row['gallery_id'],
                    'folder' => $gallery_row['folder_path'],
                    'expected' => $expected, 'downloaded' => $downloaded, 'url' => $gallery_row['url'],
                    'status_color' => $status_color, 'completed' => $is_complete_status,
                    'model_name' => $gallery_row['model_name'], 'gallery_id' => $gallery_row['gallery_id'],
                    'is_disabled' => (bool)$gallery_row['is_disabled'],
                    'thumbnails' => $thumbnails,
                    'web_path_segment' => $web_path_segment
                ];
            }
            $response = ['success' => true, 'galleries' => $galleries_data];
        
        } catch (PDOException $e) {
            error_log("Błąd DB w get_galleries_for_model: " . $e->getMessage());
            api_log("Błąd DB w get_galleries_for_model: " . $e->getMessage());
            $response['message'] = 'Błąd pobierania galerii dla modelki.';
            http_response_code(500);
        } catch (Exception $e) {
            error_log("Ogólny błąd w get_galleries_for_model: " . $e->getMessage());
            api_log("Ogólny błąd w get_galleries_for_model: " . $e->getMessage());
            $response['message'] = 'Błąd serwera przy pobieraniu galerii.';
            http_response_code(500);
        }
