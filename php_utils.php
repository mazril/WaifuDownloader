<?php
// php_utils.php

require_once 'php_config.php'; // Zawiera teraz php_db_config.php

/**
 * Czyści nazwę, aby nadawała się do użycia jako nazwa folderu/pliku.
 */
function sanitize_foldername($name) {
    if (empty($name)) { return "Nienazwana_Galeria"; }
    $name = trim((string)$name);
    $name = preg_replace('/[<>:"\/\\\\|?*\x00-\x1F\t\n\r\f\v]/', '_', $name);
    $name = preg_replace('/\s+/', ' ', $name);
    $name = trim($name);
    if (strlen($name) > 1) { $name = preg_replace('/_+/', '_', $name); $name = preg_replace('/-+/', '-', $name); }
    $name = trim($name, ' _-.');
    $max_len = 150;
    if (mb_strlen($name) > $max_len) { $name = mb_substr($name, 0, $max_len); $name = trim($name, ' _-.'); }
    return empty($name) ? "Nienazwana_Galeria" : $name;
}

/**
 * Wyciąga ID galerii z URL.
 */
function get_gallery_id_from_url($url) {
    if (empty($url) || !is_string($url)) { return "error_invalid_url_" . time(); }
    try {
        $path = parse_url($url, PHP_URL_PATH);
        $segments = explode('/', trim($path, '/'));
        $gallery_id_str = urldecode(end($segments));
        $gallery_id_str = explode('.', $gallery_id_str)[0];
        return empty($gallery_id_str) ? "error_empty_id_" . time() : $gallery_id_str;
    } catch (Exception $e) { return "error_parsing_id_" . time(); }
}

/**
 * Odczytuje listę modelek z pliku lista.txt.
 */
function read_model_list_from_file($path = LIST_FILE_PATH) {
    if (!file_exists($path)) { return []; }
    $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    $models = [];
    if ($lines) {
        foreach ($lines as $line) {
            $trimmed_line = trim($line);
            if (!empty($trimmed_line) && strpos($trimmed_line, '#') !== 0) {
                $models[] = rtrim($trimmed_line, ',');
            }
        }
    }
    return $models;
}

/**
 * Znajduje dane galerii po jej ID, przeszukując bazę danych.
 */
function find_gallery_data_by_id_db($gallery_id_to_find) {
    $pdo = get_db_connection();
    if (!$pdo) {
        error_log("find_gallery_data_by_id_db: Brak połączenia PDO.");
        return null;
    }

    try {
        $stmt = $pdo->prepare("
            SELECT g.gallery_id, g.url, g.determined_title, g.original_title, g.expected_count, m.model_name
            FROM galleries g
            JOIN models m ON g.model_id = m.model_id
            WHERE g.gallery_id = :gallery_id
        ");
        $stmt->execute([':gallery_id' => $gallery_id_to_find]);
        $result = $stmt->fetch(PDO::FETCH_ASSOC);

        if ($result) {
            return [
                "id" => $result['gallery_id'],
                "model_name" => $result['model_name'],
                "title" => $result['determined_title'] ?: $result['original_title'] ?: $result['gallery_id'],
                "count" => $result['expected_count'],
                "url" => $result['url']
            ];
        }
    } catch (PDOException $e) {
        error_log("Błąd DB w find_gallery_data_by_id_db: " . $e->getMessage());
    }
    return null;
}

/**
 * Dodaje element do kolejki priorytetowej w DB.
 */
function add_to_priority_queue_db($item_type, $item_data, $prepend = false) {
    $pdo = get_db_connection();
    if (!$pdo) {
        error_log("add_to_priority_queue_db: Brak połączenia PDO.");
        return false;
    }

    $item_data_json = json_encode($item_data);
    if ($item_data_json === false) {
        error_log("Błąd kodowania JSON w add_to_priority_queue_db dla: " . print_r($item_data, true));
        return false;
    }

    try {
        $is_present = false;
        // Sprawdzanie duplikatów
        if ($item_type === 'gallery' && isset($item_data['id'])) {
             $gallery_id_for_check = $item_data['id'];
             // Zakładamy, że item_data['id'] to string
             $stmt_check_gallery = $pdo->prepare("SELECT COUNT(*) FROM priority_queue WHERE item_type = 'gallery' AND JSON_UNQUOTE(JSON_EXTRACT(item_data, '$.id')) = :gallery_id_check");
             $stmt_check_gallery->execute([':gallery_id_check' => (string)$gallery_id_for_check]);
             if ($stmt_check_gallery->fetchColumn() > 0) {
                 $is_present = true;
             }
        } elseif (($item_type === 'scan_model' || $item_type === 'scan_model_refresh_only') && is_string($item_data)) {
            // item_data to nazwa modelki (string), item_data_json to JSON string tej nazwy (np. "\"Model Name\"")
            $stmt_check_model = $pdo->prepare("SELECT COUNT(*) FROM priority_queue WHERE item_type = :item_type AND item_data = :item_data_model_json");
            $stmt_check_model->execute([':item_type' => $item_type, ':item_data_model_json' => $item_data_json ]);
             if ($stmt_check_model->fetchColumn() > 0) {
                 $is_present = true;
             }
        }

        if ($is_present) {
            error_log("Element już jest w kolejce (sprawdzenie DB): typ='{$item_type}', dane_json='{$item_data_json}'");
            return false; // Zwróć false, jeśli element już istnieje
        }

        // Jeśli nie ma duplikatu, dodaj do bazy
        $priority_val = $prepend ? 50 : 150;
        $sql = "INSERT INTO priority_queue (item_type, item_data, priority, added_timestamp) VALUES (:item_type, :item_data_insert, :priority, NOW())";
        $stmt = $pdo->prepare($sql);
        $stmt->execute([
            ':item_type' => $item_type,
            ':item_data_insert' => $item_data_json,
            ':priority' => $priority_val
        ]);
        return $stmt->rowCount() > 0;

    } catch (PDOException $e) {
        error_log("Błąd DB w add_to_priority_queue_db: " . $e->getMessage() . " | Zapytanie z danymi: typ='{$item_type}', dane_json='{$item_data_json}'");
        return false;
    }
}


/**
 * Pobiera aktualny stan aplikacji (np. current_status) z bazy danych.
 */
function get_app_state_db($key_name) {
    $pdo = get_db_connection();
    if (!$pdo) return null;

    try {
        $stmt = $pdo->prepare("SELECT value_json FROM app_state WHERE key_name = :key_name");
        $stmt->execute([':key_name' => $key_name]);
        $result = $stmt->fetchColumn();
        if ($result) {
            return json_decode($result, true);
        }
    } catch (PDOException $e) {
        // Logowanie błędu, jeśli tabela nie istnieje lub inny problem z zapytaniem
        error_log("Błąd DB w get_app_state_db dla klucza '$key_name': " . $e->getMessage());
    }
    return null;
}

/**
 * Pobiera kolejkę priorytetową z bazy danych.
 */
function get_priority_queue_db() {
    $pdo = get_db_connection();
    if (!$pdo) return [];

    $items = [];
    try {
        $stmt = $pdo->query("SELECT item_type, item_data FROM priority_queue ORDER BY priority ASC, added_timestamp ASC");
        while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
            $decoded_data = json_decode($row['item_data'], true);
             // Jeśli item_data był prostym stringiem (np. nazwa modelu) zakodowanym jako JSON string (np. "\"ModelName\""),
             // json_decode zwróci ten string. Jeśli był obiektem JSON, zwróci tablicę asocjacyjną.
            $items[] = ["type" => $row['item_type'], "data" => $decoded_data];
        }
    } catch (PDOException $e) {
        error_log("Błąd DB w get_priority_queue_db: " . $e->getMessage());
    }
    return $items;
}

/**
 * Aktualizuje (nadpisuje) całą kolejkę priorytetową w bazie danych.
 */
function update_priority_queue_db($queue_data) {
    $pdo = get_db_connection();
    if (!$pdo) return false;

    try {
        $pdo->beginTransaction();
        $pdo->exec("DELETE FROM priority_queue");

        $sql = "INSERT INTO priority_queue (item_type, item_data, priority, added_timestamp) VALUES (:item_type, :item_data_q_update, :priority, NOW())";
        $stmt = $pdo->prepare($sql);

        foreach ($queue_data as $index => $item) {
            if (!isset($item['type']) || !array_key_exists('data', $item)) {
                error_log("Nieprawidłowy format elementu kolejki podczas update_priority_queue_db: " . print_r($item, true));
                continue; 
            }
            $item_data_json_q_update = json_encode($item['data']);
            if ($item_data_json_q_update === false) {
                error_log("Błąd kodowania JSON w update_priority_queue_db dla: " . print_r($item['data'], true));
                continue; 
            }
            $stmt->execute([
                ':item_type' => $item['type'],
                ':item_data_q_update' => $item_data_json_q_update,
                ':priority' => $index * 10 
            ]);
        }
        $pdo->commit();
        return true;
    } catch (PDOException $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        error_log("Błąd DB w update_priority_queue_db: " . $e->getMessage());
        return false;
    }
}

?>