<?php
// php_utils.php

require_once 'php_config.php';

/**
 * Czyści nazwę, aby nadawała się do użycia jako nazwa folderu/pliku.
 */
function sanitize_foldername($name) {
    if (empty($name)) {
        return "Nienazwana_Galeria";
    }
    $name = trim((string)$name);
    $name = preg_replace('/[<>:"\/\\\\|?*\x00-\x1F\t\n\r\f\v]/', '_', $name);
    $name = preg_replace('/\s+/', ' ', $name);
    $name = trim($name);
    if (strlen($name) > 1) {
        $name = preg_replace('/_+/', '_', $name);
        $name = preg_replace('/-+/', '-', $name);
    }
    $name = trim($name, ' _-.');
    $max_len = 150;
    if (mb_strlen($name) > $max_len) {
        $name = mb_substr($name, 0, $max_len);
        $name = trim($name, ' _-.');
    }
    return empty($name) ? "Nienazwana_Galeria" : $name;
}

/**
 * Wyciąga ID galerii z URL.
 */
function get_gallery_id($url) {
    if (empty($url) || !is_string($url)) {
        return "error_invalid_url_" . time();
    }
    try {
        $path = parse_url($url, PHP_URL_PATH);
        $segments = explode('/', trim($path, '/'));
        $gallery_id_str = urldecode(end($segments));
        $gallery_id_str = explode('.', $gallery_id_str)[0];
        return empty($gallery_id_str) ? "error_empty_id_" . time() : $gallery_id_str;
    } catch (Exception $e) {
        return "error_parsing_id_" . time();
    }
}

/**
 * Bezpiecznie odczytuje plik JSON.
 */
function load_json_file($filepath, $default_value = []) {
    if (!file_exists($filepath)) {
        return $default_value;
    }
    $content = file_get_contents($filepath);
    if ($content === false) {
        return $default_value;
    }
    $data = json_decode($content, true);
    return (json_last_error() === JSON_ERROR_NONE) ? $data : $default_value;
}

/**
 * Bezpiecznie zapisuje plik JSON z blokadą.
 */
function save_json_file($filepath, $data, $indent = JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE) {
    $dir = dirname($filepath);
    if (!is_dir($dir)) {
        if (!mkdir($dir, 0775, true) && !is_dir($dir)) {
             error_log("Nie udało się utworzyć katalogu: " . $dir);
             return false;
        }
    }
    $json_data = json_encode($data, $indent);
    if ($json_data === false) {
        error_log("Błąd kodowania JSON podczas zapisu do " . $filepath . ": " . json_last_error_msg());
        return false;
    }
    return file_put_contents($filepath, $json_data, LOCK_EX) !== false;
}

/**
 * Odczytuje listę modelek.
 */
function read_model_list($path = LIST_FILE_PATH) {
    if (!file_exists($path)) {
        return [];
    }
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
 * Znajduje dane galerii po jej ID, przeszukując pliki modeli.
 */
function find_gallery_data_by_id($gallery_id_to_find) {
    $models = read_model_list();
    foreach ($models as $model_name_orig) {
        $model_name_sanitized = sanitize_foldername($model_name_orig);
        $model_dir = BASE_DATA_DIR . '/' . $model_name_sanitized;
        $gallery_file = $model_dir . '/' . $model_name_sanitized . MODEL_GALLERIES_SUFFIX;

        $galleries_data = load_json_file($gallery_file);

        if (isset($galleries_data[$gallery_id_to_find]) && is_array($galleries_data[$gallery_id_to_find])) {
            $g_entry = $galleries_data[$gallery_id_to_find];
            return [
                "id" => $gallery_id_to_find, // Klucz 'id' zawiera samo ID galerii
                "model_name" => $model_name_orig,
                "title" => $g_entry['determined_title'] ?? $g_entry['original_title_from_list'] ?? $gallery_id_to_find,
                "count" => $g_entry['expected_count'] ?? null
            ];
        }
    }
    return null;
}

/**
 * Dodaje element do kolejki priorytetowej (z blokadą).
 * Zmieniono strukturę: dane elementu są teraz pod kluczem "data".
 */
function add_to_priority_queue($item_type, $item_data, $prepend = false) {
    $queue = load_json_file(PRIORITY_QUEUE_FILE_PATH, []);
    
    // Nowa struktura elementu kolejki
    $new_item = [
        "type" => $item_type,
        "data" => $item_data // Przechowuj cały $item_data (słownik lub string) pod kluczem "data"
    ];

    // Logika sprawdzania duplikatów musi teraz zaglądać do 'data'
    $is_present = false;
    foreach ($queue as $item_in_queue) {
        if (isset($item_in_queue['type']) && $item_in_queue['type'] === $new_item['type'] && isset($item_in_queue['data'])) {
            $queued_data_payload = $item_in_queue['data'];
            $new_data_payload = $new_item['data']; // To jest $item_data

            if ($new_item['type'] === 'gallery') {
                // $queued_data_payload i $new_data_payload powinny być słownikami
                if (is_array($queued_data_payload) && is_array($new_data_payload) &&
                    isset($queued_data_payload['id']) && isset($new_data_payload['id']) && // Sprawdzamy ID wewnątrz "data"
                    $queued_data_payload['id'] === $new_data_payload['id']) {
                    $is_present = true;
                    break;
                }
            } elseif ($new_item['type'] === 'scan_model') {
                // $queued_data_payload i $new_data_payload powinny być stringami (nazwami modeli)
                if ($queued_data_payload === $new_data_payload) {
                    $is_present = true;
                    break;
                }
            }
        }
    }

    if (!$is_present) {
        if ($prepend) {
            array_unshift($queue, $new_item);
        } else {
            $queue[] = $new_item;
        }
        if (save_json_file(PRIORITY_QUEUE_FILE_PATH, $queue)) {
            return true;
        } else {
            error_log("Błąd zapisu kolejki w add_to_priority_queue dla: " . json_encode($new_item));
            return false;
        }
    }
    error_log("Element już jest w kolejce lub duplikat (PHP): " . json_encode($new_item['data']));
    return false; // Już jest w kolejce
}
?>