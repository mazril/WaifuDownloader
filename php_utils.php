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
function get_gallery_id_from_url($url) { // Zmieniono nazwę dla jasności
    if (empty($url) || !is_string($url)) { return "error_invalid_url_" . time(); }
    try {
        $path = parse_url($url, PHP_URL_PATH);
        $segments = explode('/', trim($path, '/'));
        $gallery_id_str = urldecode(end($segments));
        // Dodatkowe czyszczenie, jeśli ID zawiera np. rozszerzenie pliku (choć nie powinno z URL galerii)
        $gallery_id_str = explode('.', $gallery_id_str)[0];
        return empty($gallery_id_str) ? "error_empty_id_" . time() : $gallery_id_str;
    } catch (Exception $e) { return "error_parsing_id_" . time(); }
}

/**
 * Odczytuje listę modelek z pliku lista.txt.
 */
function read_model_list_from_file($path = LIST_FILE_PATH) { // Zmieniono nazwę dla jasności
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
function find_gallery_data_by_id_db($gallery_id_to_find) { // Zmieniono nazwę dla jasności
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
                "url" => $result['url'] // Dodajemy URL, może być przydatne
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

    // Logika sprawdzania duplikatów
    $is_present = false;
    try {
        $check_query_sql = "SELECT COUNT(*) FROM priority_queue WHERE item_type = :item_type AND item_data = :item_data";
        $stmt_check = $pdo->prepare($check_query_sql);

        // Dla typu 'gallery', sprawdzamy duplikat na podstawie gallery_id wewnątrz JSONa
        // Ta część jest skomplikowana do zrobienia w czystym SQL bez funkcji JSON specyficznych dla wersji MySQL.
        // Prostsze podejście: pobierz kolejkę i sprawdź w PHP (jak w wersji plikowej), lub zaakceptuj potencjalne duplikaty
        // na krótką metę i pozwól Pythonowi je obsłużyć/usunąć.
        // Tutaj zaimplementujemy proste sprawdzenie po całym item_data_json.
        // Idealnie, Python powinien być głównym zarządcą kolejki, a PHP tylko dodawać.

        // Dla uproszczenia, zakładamy, że Python obsłuży dokładniejsze deduplikacje.
        // $stmt_check->execute([':item_type' => $item_type, ':item_data' => $item_data_json]);
        // if ($stmt_check->fetchColumn() > 0) {
        //     $is_present = true;
        // }

        // Dla bardziej precyzyjnego sprawdzenia dla galerii (jeśli MySQL > 5.7.8):
        if ($item_type === 'gallery' && isset($item_data['id'])) {
             $gallery_id_for_check = $item_data['id'];
             $stmt_check_gallery = $pdo->prepare("SELECT COUNT(*) FROM priority_queue WHERE item_type = 'gallery' AND JSON_UNQUOTE(JSON_EXTRACT(item_data, '$.id')) = :gallery_id");
             $stmt_check_gallery->execute([':gallery_id' => $gallery_id_for_check]);
             if ($stmt_check_gallery->fetchColumn() > 0) {
                 $is_present = true;
             }
        } elseif ($item_type === 'scan_model' || $item_type === 'scan_model_refresh_only') {
            // Dla scan_model, item_data to string z nazwą modelki
            $stmt_check_model = $pdo->prepare("SELECT COUNT(*) FROM priority_queue WHERE item_type = :item_type AND item_data = :item_data_model");
            $stmt_check_model->execute([':item_type' => $item_type, ':item_data_model' => $item_data_json ]); // item_data jest już JSON-em stringa
             if ($stmt_check_model->fetchColumn() > 0) {
                 $is_present = true;
             }
        }


        if ($is_present) {
            error_log("Element już jest w kolejce (sprawdzenie DB): " . $item_type . " - " . $item_data_json);
            return false;
        }

        // Logika priorytetu: jeśli prepend, ustawiamy niższy (lepszy) priorytet.
        // Prosty sposób: items dodane z prepend dostają priorytet < 0, reszta >= 0.
        // Lub bardziej złożone: odczytaj max/min i dostosuj.
        // Tutaj uproszczone: nowe elementy dodawane przez PHP mogą dostać np. 50 (prepend) lub 150 (append)
        // a Python może używać np. 100.
        $priority_val = $prepend ? 50 : 150;

        $sql = "INSERT INTO priority_queue (item_type, item_data, priority, added_timestamp) VALUES (:item_type, :item_data, :priority, NOW())";
        $stmt = $pdo->prepare($sql);
        $stmt->execute([
            ':item_type' => $item_type,
            ':item_data' => $item_data_json,
            ':priority' => $priority_val
        ]);
        return $stmt->rowCount() > 0;

    } catch (PDOException $e) {
        error_log("Błąd DB w add_to_priority_queue_db: " . $e->getMessage() . " | Dane: " . $item_data_json);
        return false;
    }
}


/**
 * Pobiera aktualny stan aplikacji (np. current_status) z bazy danych.
 * @param string $key Klucz stanu do pobrania.
 * @return array|null Dane stanu lub null w przypadku błędu/braku.
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
        error_log("Błąd DB w get_app_state_db dla klucza '$key_name': " . $e->getMessage());
    }
    return null;
}

/**
 * Pobiera kolejkę priorytetową z bazy danych.
 * @return array Kolejka priorytetowa.
 */
function get_priority_queue_db() {
    $pdo = get_db_connection();
    if (!$pdo) return [];

    $items = [];
    try {
        $stmt = $pdo->query("SELECT item_type, item_data FROM priority_queue ORDER BY priority ASC, added_timestamp ASC");
        while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
            $data = json_decode($row['item_data'], true);
            // Poprawka dla scan_model, gdzie item_data to string (nazwa modelki), a nie JSON dict
            if (json_last_error() !== JSON_ERROR_NONE && ($row['item_type'] === 'scan_model' || $row['item_type'] === 'scan_model_refresh_only')) {
                // Jeśli item_data nie jest prawidłowym JSON-em, a typ to scan_model,
                // zakładamy, że item_data to bezpośrednio nazwa modelki (string)
                // W bazie danych jest przechowywany jako JSON string np. "\"Model Name\""
                // json_decode poprawnie to obsłuży. Jeśli byłby goły string, to by był błąd.
                // W tym przypadku nie ma potrzeby specjalnej obsługi, json_decode powinien dać string.
            }
             $items[] = ["type" => $row['item_type'], "data" => $data];
        }
    } catch (PDOException $e) {
        error_log("Błąd DB w get_priority_queue_db: " . $e->getMessage());
    }
    return $items;
}

/**
 * Aktualizuje (nadpisuje) całą kolejkę priorytetową w bazie danych.
 * @param array $queue_data Nowa kolejka.
 * @return bool Sukces/porażka.
 */
function update_priority_queue_db($queue_data) {
    $pdo = get_db_connection();
    if (!$pdo) return false;

    try {
        $pdo->beginTransaction();
        $pdo->exec("DELETE FROM priority_queue");

        $sql = "INSERT INTO priority_queue (item_type, item_data, priority, added_timestamp) VALUES (:item_type, :item_data, :priority, NOW())";
        $stmt = $pdo->prepare($sql);

        foreach ($queue_data as $index => $item) {
            if (!isset($item['type']) || !array_key_exists('data', $item)) {
                error_log("Nieprawidłowy format elementu kolejki podczas update_priority_queue_db: " . print_r($item, true));
                continue; // Pomiń nieprawidłowy element
            }
            $item_data_json = json_encode($item['data']);
            if ($item_data_json === false) {
                error_log("Błąd kodowania JSON w update_priority_queue_db dla: " . print_r($item['data'], true));
                continue; // Pomiń element, którego nie można zakodować
            }
            $stmt->execute([
                ':item_type' => $item['type'],
                ':item_data' => $item_data_json,
                ':priority' => $index * 10 // Prosty priorytet oparty na kolejności
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