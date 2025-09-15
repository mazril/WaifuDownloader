<?php
// Extracted from api.php case 'get_global_ai_settings'
$python_config = get_python_config();
        if ($python_config && isset($python_config['ai_settings'])) {
            $response = ['success' => true, 'settings' => $python_config['ai_settings']];
        } else {
            $response['message'] = "Nie udało się odczytać globalnych ustawień AI z pliku config.json.";
            http_response_code(500);
        }
