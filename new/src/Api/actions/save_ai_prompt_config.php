<?php
// Extracted from api.php case 'save_ai_prompt_config'
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
            $config_data_save = json_decode($raw_post_data, true); 
            
            $config_id_save = $config_data_save['config_id'] ?? null; 
            $system_prompt_save = $config_data_save['system_prompt'] ?? null; 

            if (!$config_id_save || $system_prompt_save === null) {
                http_response_code(400);
                $response['message'] = 'Nie podano ID konfiguracji lub treści promptu.';
                break;
            }
            $model_name_save = !empty($config_data_save['ollama_model_name']) ? $config_data_save['ollama_model_name'] : null;
            $temp_save = isset($config_data_save['ollama_temperature']) ? (float)$config_data_save['ollama_temperature'] : 0.2;
            $num_pred_save = isset($config_data_save['ollama_num_predict']) ? (int)$config_data_save['ollama_num_predict'] : 60;
            $top_p_save = isset($config_data_save['ollama_top_p']) ? (float)$config_data_save['ollama_top_p'] : 0.8;
            $desc_save = $config_data_save['description'] ?? '';

            try {
                $sql_save_config = "UPDATE ai_prompt_configs SET 
                                        system_prompt = :system_prompt, 
                                        ollama_model_name = :ollama_model_name,
                                        ollama_temperature = :ollama_temperature,
                                        ollama_num_predict = :ollama_num_predict,
                                        ollama_top_p = :ollama_top_p,
                                        description = :description
                                    WHERE config_id = :config_id"; 
                $stmt_save_config = $pdo->prepare($sql_save_config); 
                $stmt_save_config->execute([
                    ':system_prompt' => $system_prompt_save,
                    ':ollama_model_name' => $model_name_save,
                    ':ollama_temperature' => $temp_save,
                    ':ollama_num_predict' => $num_pred_save,
                    ':ollama_top_p' => $top_p_save,
                    ':description' => $desc_save,
                    ':config_id' => $config_id_save
                ]);
                if ($stmt_save_config->rowCount() > 0) {
                    $response = ['success' => true, 'message' => "Konfiguracja AI '$config_id_save' została zaktualizowana."];
                } else {
                    $check_stmt_save_config = $pdo->prepare("SELECT COUNT(*) FROM ai_prompt_configs WHERE config_id = :config_id"); 
                    $check_stmt_save_config->execute([':config_id' => $config_id_save]);
                    if ($check_stmt_save_config->fetchColumn() > 0) {
                        $response = ['success' => true, 'message' => "Konfiguracja AI '$config_id_save' nie wymagała aktualizacji (brak zmian)."];
                    } else {
                        $response['message'] = "Konfiguracja AI '$config_id_save' nie została znaleziona (nie utworzono nowej).";
                         http_response_code(404); 
                    }
                }
            } catch (PDOException $e) {
                error_log("Błąd DB w save_ai_prompt_config: " . $e->getMessage());
                api_log("Błąd DB w save_ai_prompt_config: " . $e->getMessage());
                $response['message'] = "Błąd bazy danych przy zapisie konfiguracji AI: " . $e->getMessage();
                http_response_code(500);
            }
        } else {
            http_response_code(405);
            $response['message'] = 'Metoda niedozwolona (wymagany POST).';
        }
