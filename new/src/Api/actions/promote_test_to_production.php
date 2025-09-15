<?php
// Extracted from api.php case 'promote_test_to_production'
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
            if (!$pdo) { $response['message'] = 'Brak połączenia z DB.'; http_response_code(503); break; }
            try {
                $stmt_get_test_config = $pdo->prepare("SELECT * FROM ai_prompt_configs WHERE config_id = 'test'"); 
                $stmt_get_test_config->execute();
                $test_config_data = $stmt_get_test_config->fetch(PDO::FETCH_ASSOC); 

                if ($test_config_data) {
                    $sql_prod_update_from_test = "UPDATE ai_prompt_configs SET 
                                                    system_prompt = :system_prompt, 
                                                    ollama_model_name = :ollama_model_name,
                                                    ollama_temperature = :ollama_temperature,
                                                    ollama_num_predict = :ollama_num_predict,
                                                    ollama_top_p = :ollama_top_p,
                                                    description = :description 
                                                WHERE config_id = 'production'"; 
                    $stmt_prod_update = $pdo->prepare($sql_prod_update_from_test); 
                    $stmt_prod_update->execute([
                        ':system_prompt' => $test_config_data['system_prompt'],
                        ':ollama_model_name' => $test_config_data['ollama_model_name'],
                        ':ollama_temperature' => $test_config_data['ollama_temperature'],
                        ':ollama_num_predict' => $test_config_data['ollama_num_predict'],
                        ':ollama_top_p' => $test_config_data['ollama_top_p'],
                        ':description' => $test_config_data['description'] . " (Promoted from test " . date("Y-m-d H:i:s") . ")"
                    ]);
                    $response = ['success' => true, 'message' => 'Konfiguracja testowa została przeniesiona do produkcji.'];
                } else {
                    $response['message'] = 'Nie znaleziono konfiguracji testowej do promocji.';
                    http_response_code(404); 
                }
            } catch (PDOException $e) {
                error_log("Błąd DB w promote_test_to_production: " . $e->getMessage());
                api_log("Błąd DB w promote_test_to_production: " . $e->getMessage());
                $response['message'] = "Błąd bazy danych: " . $e->getMessage();
                http_response_code(500);
            }
        } else {
            http_response_code(405);
            $response['message'] = 'Metoda niedozwolona (wymagany POST).';
        }
