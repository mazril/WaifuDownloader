<?php
// ai_worker.php (lub część testai.php wywoływana np. z crona / jako CLI worker)
require_once 'php_config.php';
require_once 'php_utils.php'; 

/**
 * Wywołuje API Ollamy z danymi z konfiguracji.
 * Opis: Bez zmian w tej funkcji.
 */
function call_ollama_api($system_prompt, $user_prompt, $ollama_config, $python_config = []) {
    $ai_settings = $python_config['ai_settings'] ?? [];
    $ollama_api_base_url = $ai_settings['api_base_url']['value'] ?? 'http://localhost:11434';
    $default_model_from_config = $ai_settings['default_model_name']['value'] ?? 'llama3:latest';
    
    $model_to_use = $ollama_config['ollama_model_name'] ?: $default_model_from_config;

    $full_prompt = $system_prompt . "\n\n" . $user_prompt;
    
    $payload = [
        "model" => $model_to_use,
        "prompt" => $full_prompt,
        "stream" => false,
        "options" => [
            "temperature" => (float)($ollama_config['ollama_temperature'] ?? 0.2),
            "num_predict" => (int)($ollama_config['ollama_num_predict'] ?? 60),
            "top_p" => (float)($ollama_config['ollama_top_p'] ?? 0.8),
            "stop" => ["\n", "User:", "System:"]
        ]
    ];

    $ch = curl_init($ollama_api_base_url . '/api/generate');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_POST, true);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    curl_setopt($ch, CURLOPT_TIMEOUT, 90);

    $response_json = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curl_error = curl_error($ch);
    curl_close($ch);

    if ($curl_error) {
        error_log("AI Worker: Błąd cURL przy komunikacji z Ollama: " . $curl_error);
        return "Błąd: Komunikacja cURL z Ollama";
    }
    if ($http_code >= 400) {
        error_log("AI Worker: Ollama API zwróciło błąd HTTP $http_code. Odpowiedź: $response_json");
        return "Błąd: Odpowiedź HTTP $http_code z Ollama";
    }

    $result = json_decode($response_json, true);
    if (json_last_error() !== JSON_ERROR_NONE || !isset($result['response'])) {
        error_log("AI Worker: Błąd dekodowania JSON lub brak klucza 'response' z Ollama. Surowa odp: " . $response_json);
        return "Błąd: Niepoprawna odpowiedź JSON z Ollama";
    }
    
    $ai_title = trim($result['response']);
    if (stripos($ai_title, "title:") === 0) $ai_title = trim(substr($ai_title, strlen("title:")));
    if (stripos($ai_title, "desired gallery title:") === 0) $ai_title = trim(substr($ai_title, strlen("desired gallery title:")));
    $ai_title = trim($ai_title, '"\'');

    return $ai_title;
}

function post_process_ai_title_php($raw_title_from_ai, $model_name_to_avoid = null) {
    if (strpos($raw_title_from_ai, "Błąd") === 0 || empty($raw_title_from_ai)) {
        return "";
    }
    $cleaned_title = preg_replace("/^\s*(title|tytuł|Desired Gallery Title)\s*:\s*/i", "", $raw_title_from_ai);
    $cleaned_title = trim($cleaned_title, "\"\'");

    $cleaned_title = preg_replace("/\s*-\s*\d+\s*(photos|images|pics|zdjęć|obrazków|fotografii|sets|vids|videos|файлов)\s*$/i", "", $cleaned_title);
    $cleaned_title = preg_replace("/\s+by\s+[\w\s.-]+$/i", "", $cleaned_title);

    $stop_phrases = [
        "N/A", "Exclusive Set", "Onlyfans", "Patreon", "Fansly", "Leaks", "Leaked", "Cosplay",
        "Model:", "Character:", "Series:", "Original Character", "Original", "OC"
    ];
    foreach ($stop_phrases as $phrase) {
        $cleaned_title = preg_replace("/(^|\s|-)" . preg_quote($phrase, '/') . "($|\s|-)/i", "$1$2", $cleaned_title);
    }

    $cleaned_title = trim(preg_replace('/\s*-\s*/', ' - ', preg_replace('/\s+/', ' ', trim($cleaned_title, ' -'))));
    
    if ($model_name_to_avoid && !empty($model_name_to_avoid)) {
        if (stripos($cleaned_title, $model_name_to_avoid) !== false) {
            error_log("AI Worker (post-process): Wykryto nazwę modelki '$model_name_to_avoid' w tytule '$cleaned_title'. Odrzucam.");
            return "";
        }
    }

    return (strlen($cleaned_title) < 3) ? "" : $cleaned_title;
}


function run_ai_worker() {
    $pdo = get_db_connection();
    if (!$pdo) {
        error_log("AI Worker: Brak połączenia z bazą danych.");
        return;
    }
    
    $python_config = get_python_config();
    if (!$python_config) {
        error_log("AI Worker: Nie udało się załadować konfiguracji Pythona (config.json). Przerywam cykl.");
        return;
    }
    
    echo "AI Worker uruchomiony o " . date('Y-m-d H:i:s') . "\n";

    // --- Przetwarzanie Produkcyjne AI ---
    $stmt_prod = $pdo->prepare("
        SELECT g.gallery_id, g.source_page_title, g.original_title, g.gallery_description, g.tags_json, m.model_name
        FROM galleries g
        JOIN models m ON g.model_id = m.model_id
        WHERE g.status = 'pending_production_ai' AND g.initial_data_fetched = TRUE
        ORDER BY g.updated_at ASC LIMIT 5 
    ");
    $stmt_prod->execute();
    $galleries_for_prod_ai = $stmt_prod->fetchAll(PDO::FETCH_ASSOC);

    if (count($galleries_for_prod_ai) > 0) {
         echo "Znaleziono " . count($galleries_for_prod_ai) . " galerii do analizy produkcyjnej AI.\n";
        $prod_config_stmt = $pdo->query("SELECT * FROM ai_prompt_configs WHERE config_id = 'production'");
        $prod_ai_config = $prod_config_stmt->fetch(PDO::FETCH_ASSOC);

        if (!$prod_ai_config) {
            error_log("AI Worker: Brak konfiguracji promptu 'production' w bazie.");
        } else {
            foreach ($galleries_for_prod_ai as $gallery) {
                echo "  Przetwarzanie (Prod AI) galerii: " . $gallery['gallery_id'] . "\n";
                $text_to_process = $gallery['source_page_title'] ?: $gallery['original_title'] ?: $gallery['gallery_id'];
                $description_from_db_php = $gallery['gallery_description'] ?? null;
                $tags = $gallery['tags_json'] ? json_decode($gallery['tags_json'], true) : [];
                $character_hint = $tags['cosplay'][0] ?? null;
                $series_hint = $tags['fandom'][0] ?? null;

                $user_prompt = "Text: \"{$text_to_process}\"\n";
                if ($description_from_db_php) $user_prompt .= "Contextual Description: {$description_from_db_php}\n";
                if ($gallery['model_name']) $user_prompt .= "Forbidden Model Name: {$gallery['model_name']}\n";
                if ($character_hint) $user_prompt .= "Character Hint: {$character_hint}\n";
                if ($series_hint) $user_prompt .= "Series Hint: {$series_hint}\n";
                $user_prompt .= "Desired Gallery Title:";
                
                $raw_ai_title = call_ollama_api($prod_ai_config['system_prompt'], $user_prompt, $prod_ai_config, $python_config);
                $final_title = post_process_ai_title_php($raw_ai_title, $gallery['model_name']);

                if (!empty($final_title)) {
                    $update_stmt = $pdo->prepare("UPDATE galleries SET determined_title = :title, status = 'pending_check' WHERE gallery_id = :id");
                    $update_stmt->execute([':title' => $final_title, ':id' => $gallery['gallery_id']]);
                    echo "    Sukces (Prod AI): " . $gallery['gallery_id'] . " -> " . $final_title . "\n";
                } else {
                    $update_stmt = $pdo->prepare("UPDATE galleries SET status = 'error_ai_prod' WHERE gallery_id = :id");
                    $update_stmt->execute([':id' => $gallery['gallery_id']]);
                    error_log("AI Worker (Prod): Nie udało się uzyskać tytułu dla " . $gallery['gallery_id'] . ". Surowa odp: " . $raw_ai_title);
                    echo "    Błąd (Prod AI): " . $gallery['gallery_id'] . ". Surowa odp: " . $raw_ai_title . "\n";
                }
                sleep(1);
            }
        }
    } else {
        echo "Brak galerii do analizy produkcyjnej AI.\n";
    }

    // --- Przetwarzanie Testowe AI ---
    $stmt_test = $pdo->prepare("
        SELECT g.gallery_id, g.source_page_title, g.original_title, g.gallery_description, g.tags_json, m.model_name
        FROM galleries g
        JOIN models m ON g.model_id = m.model_id
        WHERE g.status = 'pending_test_ai' AND g.initial_data_fetched = TRUE
        ORDER BY g.updated_at ASC LIMIT 5
    ");
    $stmt_test->execute();
    $galleries_for_test_ai = $stmt_test->fetchAll(PDO::FETCH_ASSOC);
    
    if (count($galleries_for_test_ai) > 0) {
        echo "Znaleziono " . count($galleries_for_test_ai) . " galerii do analizy testowej AI.\n";
        $test_config_stmt = $pdo->query("SELECT * FROM ai_prompt_configs WHERE config_id = 'test'");
        $test_ai_config = $test_config_stmt->fetch(PDO::FETCH_ASSOC);

        if (!$test_ai_config) {
            error_log("AI Worker: Brak konfiguracji promptu 'test' w bazie.");
        } else {
            foreach ($galleries_for_test_ai as $gallery) {
                 echo "  Przetwarzanie (Test AI) galerii: " . $gallery['gallery_id'] . "\n";
                $text_to_process = $gallery['source_page_title'] ?: $gallery['original_title'] ?: $gallery['gallery_id'];
                $description_from_db_php = $gallery['gallery_description'] ?? null;
                $tags = $gallery['tags_json'] ? json_decode($gallery['tags_json'], true) : [];
                $character_hint = $tags['cosplay'][0] ?? null;
                $series_hint = $tags['fandom'][0] ?? null;

                $user_prompt = "Text: \"{$text_to_process}\"\n";
                if ($description_from_db_php) $user_prompt .= "Contextual Description: {$description_from_db_php}\n";
                if ($gallery['model_name']) $user_prompt .= "Forbidden Model Name: {$gallery['model_name']}\n";
                if ($character_hint) $user_prompt .= "Character Hint: {$character_hint}\n";
                if ($series_hint) $user_prompt .= "Series Hint: {$series_hint}\n";
                $user_prompt .= "Desired Gallery Title:";

                $raw_ai_title = call_ollama_api($test_ai_config['system_prompt'], $user_prompt, $test_ai_config, $python_config);
                $final_title = post_process_ai_title_php($raw_ai_title, $gallery['model_name']);

                if (!empty($final_title)) {
                    $update_stmt = $pdo->prepare("UPDATE galleries SET test_ai_title = :title, status = 'test_completed' WHERE gallery_id = :id");
                    $update_stmt->execute([':title' => $final_title, ':id' => $gallery['gallery_id']]);
                     echo "    Sukces (Test AI): " . $gallery['gallery_id'] . " -> " . $final_title . "\n";
                } else {
                    $update_stmt = $pdo->prepare("UPDATE galleries SET status = 'error_ai_test' WHERE gallery_id = :id");
                    $update_stmt->execute([':id' => $gallery['gallery_id']]);
                    error_log("AI Worker (Test): Nie udało się uzyskać tytułu dla " . $gallery['gallery_id'] . ". Surowa odp: " . $raw_ai_title);
                    echo "    Błąd (Test AI): " . $gallery['gallery_id'] . ". Surowa odp: " . $raw_ai_title . "\n";
                }
                 sleep(1);
            }
        }
    } else {
         echo "Brak galerii do analizy testowej AI.\n";
    }
    echo "AI Worker zakończył pracę o " . date('Y-m-d H:i:s') . "\n\n";
}

// Ta część pozostaje bez zmian
// if (php_sapi_name() == 'cli') {
//     run_ai_worker();
// }
?>