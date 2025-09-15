<?php
// Extracted from api.php case 'get_ai_prompt_configs'
try {
            if (!$pdo) { throw new Exception("Brak połączenia z bazą danych dla get_ai_prompt_configs."); }
            $stmt = $pdo->query("SELECT config_id, system_prompt, ollama_model_name, ollama_temperature, ollama_num_predict, ollama_top_p, description FROM ai_prompt_configs");
            $configs = $stmt->fetchAll(PDO::FETCH_ASSOC);
            $response = ['success' => true, 'configs' => $configs];
        } catch (PDOException $e) {
            error_log("Błąd DB w get_ai_prompt_configs: " . $e->getMessage());
            api_log("Błąd DB w get_ai_prompt_configs: " . $e->getMessage());
            $response['message'] = "Błąd bazy danych przy pobieraniu konfiguracji AI: " . $e->getMessage();
            http_response_code(500);
        } catch (Exception $e) {
            error_log("Ogólny błąd w get_ai_prompt_configs: " . $e->getMessage());
            api_log("Ogólny błąd w get_ai_prompt_configs: " . $e->getMessage());
            $response['message'] = "Błąd serwera przy pobieraniu konfiguracji AI: " . $e->getMessage();
            http_response_code(500);
        }
