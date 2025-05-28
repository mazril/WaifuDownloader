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
function get_gallery_id($url) {
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
 * Odczytuje listę modelek.
 */
function read_model_list($path = LIST_FILE_PATH) {
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
function find_gallery_data_by_id($gallery_id_to_find) {
    $pdo = get_db_connection();
    if (!$pdo) return null;

    try {
        $stmt = $pdo->prepare("
            SELECT g.gallery_id, g.determined_title, g.original_title, g.expected_count, m.model_name
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
                "title" => $result['determined_title'] ?? $result['original_title'] ?? $result['gallery_id'],
                "count" => $result['expected_count'] ?? null
            ];
        }