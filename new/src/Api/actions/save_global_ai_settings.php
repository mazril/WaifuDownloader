<?php
// Extracted from api.php case 'save_global_ai_settings'
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            $new_settings_data = json_decode($raw_post_data, true);
            if (json_last_error() !== JSON_ERROR_NONE || !is_array($new_settings_data)) {
                $response['message'] = "Nieprawidłowy format danych JSON.";
                http_response_code(400);
                break;
            }

            $config_path = __DIR__ . '/config.json';
            if (!is_writable($config_path)) {
                 $response['message'] = "Błąd uprawnień: Plik config.json nie jest zapisywalny przez serwer.";
                 http_response_code(500);
                 break;
            }

            $current_full_config = get_python_config();
            if (!$current_full_config) {
                $response['message'] = "Nie udało się odczytać istniejącego pliku config.json.";
                http_response_code(500);
                break;
            }
            
            if (isset($new_settings_data['api_base_url']) && isset($current_full_config['ai_settings']['api_base_url'])) {
                $current_full_config['ai_settings']['api_base_url']['value'] = trim($new_settings_data['api_base_url']);
            }
            if (isset($new_settings_data['default_model_name']) && isset($current_full_config['ai_settings']['default_model_name'])) {
                $current_full_config['ai_settings']['default_model_name']['value'] = trim($new_settings_data['default_model_name']);
            }

            $new_json_content = json_encode($current_full_config, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
            
            if (file_put_contents($config_path, $new_json_content) !== false) {
                $response = ['success' => true, 'message' => 'Globalne ustawienia AI zostały zaktualizowane.'];
            } else {
                $response['message'] = "Nie udało się zapisać zmian do pliku config.json.";
                http_response_code(500);
            }
        } else {
            http_response_code(405);
            $response['message'] = 'Metoda niedozwolona (wymagany POST).';
        }
