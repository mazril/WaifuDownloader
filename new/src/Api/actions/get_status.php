<?php
// Extracted from api.php case 'get_status'
$status_data = get_app_state_db('current_status');
        if ($status_data && is_array($status_data)) {
            $defaults = [
                "timestamp" => date("Y-m-d H:i:s"), "message" => "Brak danych statusu.",
                "current_model" => "", "current_gallery_title" => "", "current_gallery_id" => null,
                "current_download_count" => null, "scan_session_found_count" => null,
                "current_expected_count" => null, "is_processing" => false
            ];
            $response = array_merge($defaults, $status_data);
        } else {
            $response = [
                "timestamp" => date("Y-m-d H:i:s"), "message" => "Oczekiwanie na pierwszy status ze skryptu Python (DB)...",
                "current_model" => "", "current_gallery_title" => "", "current_gallery_id" => null,
                "current_download_count" => null, "scan_session_found_count" => null,
                "current_expected_count" => null, "is_processing" => false
            ];
        }
