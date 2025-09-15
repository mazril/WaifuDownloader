<?php
// Extracted from api.php case 'add_model'
if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
        $model_name_param = trim($_GET['model_name'] ?? '');
        if (empty($model_name_param)) {
            $response['message'] = "Nie podano nazwy modelki.";
            http_response_code(400);
            break;
        }

        try {
            $sanitized_name = sanitize_foldername($model_name_param);
            
            $stmt_check = $pdo->prepare("SELECT model_id FROM models WHERE model_name = :model_name OR sanitized_name = :sanitized_name");
            $stmt_check->execute([':model_name' => $model_name_param, ':sanitized_name' => $sanitized_name]);
            if ($stmt_check->fetch()) {
                $response['message'] = "Modelka '$model_name_param' (lub jej znormalizowana forma) już istnieje w bazie danych.";
                $response['success'] = true; 
            } else {
                $stmt_insert = $pdo->prepare("INSERT INTO models (model_name, sanitized_name) VALUES (:model_name, :sanitized_name)");
                $stmt_insert->execute([':model_name' => $model_name_param, ':sanitized_name' => $sanitized_name]);
                if ($stmt_insert->rowCount() > 0) {
                    $response = ['success' => true, 'message' => "Modelka '$model_name_param' dodana do bazy danych."];
                    clear_models_cache();
                } else {
                    $response['message'] = "Nie udało się dodać modelki '$model_name_param' do bazy danych.";
                     http_response_code(500);
                }
            }
        } catch (PDOException $e) {
            error_log("Błąd DB w akcji add_model: " . $e->getMessage());
            api_log("Błąd DB w akcji add_model: " . $e->getMessage());
            $response['message'] = "Błąd bazy danych podczas dodawania modelki: " . $e->getMessage();
            http_response_code(500);
        }
