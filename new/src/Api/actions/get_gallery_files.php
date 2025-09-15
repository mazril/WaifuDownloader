<?php
// Extracted from api.php case 'get_gallery_files'
$gallery_id = $_GET['gallery_id'] ?? null;
        if (!$gallery_id) {
            $response['message'] = "Nie podano ID galerii.";
            break;
        }
        try {
            if (!$pdo) throw new Exception("Brak połączenia z bazą danych dla get_gallery_files.");
            $stmt = $pdo->prepare("
                SELECT g.folder_path, m.sanitized_name as model_sanitized_name
                FROM galleries g
                JOIN models m ON g.model_id = m.model_id
                WHERE g.gallery_id = :gallery_id
            ");
            $stmt->execute([':gallery_id' => $gallery_id]);
            $gallery_data_db = $stmt->fetch(PDO::FETCH_ASSOC); 

            if (!$gallery_data_db || empty($gallery_data_db['folder_path'])) {
                $response['message'] = "Nie znaleziono ścieżki folderu dla galerii o ID: " . htmlspecialchars($gallery_id) . " lub ścieżka jest pusta.";
                $response['success'] = true; 
                $response['files'] = [];
                $response['web_path_segment'] = ''; 
                break;
            }
            $absolute_folder_path = $gallery_data_db['folder_path'];
            $model_sanitized_name = $gallery_data_db['model_sanitized_name'];
            $gallery_folder_name_only = basename($absolute_folder_path);
            
            $web_path_segment = defined('BASE_DATA_DIR_NAME') ? BASE_DATA_DIR_NAME : "Modelki";
            $web_path_segment .= '/' . $model_sanitized_name . '/' . $gallery_folder_name_only;


            if (!is_dir($absolute_folder_path)) {
                $response['message'] = "Folder galerii nie istnieje na serwerze: " . htmlspecialchars($absolute_folder_path);
                $response['files'] = [];
                $response['web_path_segment'] = $web_path_segment;
                $response['success'] = true; 
                break;
            }
            $allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp'];
            $files = [];
            if (is_readable($absolute_folder_path)) {
                $dir_iterator = new DirectoryIterator($absolute_folder_path);
                foreach ($dir_iterator as $fileinfo) {
                    if ($fileinfo->isFile()) {
                        $extension = strtolower($fileinfo->getExtension());
                        if (in_array($extension, $allowed_extensions)) {
                            $files[] = $fileinfo->getFilename();
                        }
                    }
                }
                natsort($files); 
            } else {
                error_log("Nie można odczytać katalogu: " . $absolute_folder_path);
                api_log("Nie można odczytać katalogu: " . $absolute_folder_path);
                $response['message'] = "Nie można odczytać zawartości folderu galerii na serwerze.";
            }
             
            $response = [
                'success' => true,
                'files' => array_values($files), 
                'web_path_segment' => $web_path_segment,
                'gallery_id' => $gallery_id
            ];
        } catch (PDOException $e) {
            error_log("Błąd DB w get_gallery_files dla ID '$gallery_id': " . $e->getMessage());
            api_log("Błąd DB w get_gallery_files dla ID '$gallery_id': " . $e->getMessage());
            $response['message'] = "Błąd bazy danych podczas pobierania informacji o galerii.";
            http_response_code(500);
        } catch (Exception $e) {
            error_log("Inny błąd w get_gallery_files dla ID '$gallery_id': " . $e->getMessage());
            api_log("Inny błąd w get_gallery_files dla ID '$gallery_id': " . $e->getMessage());
            $response['message'] = "Wystąpił nieoczekiwany błąd serwera: " . $e->getMessage();
            http_response_code(500);
        }
