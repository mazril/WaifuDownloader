<?php
namespace App\\Utils;

class Sanitizer {
    public static function sanitizeFoldername($name) {
        if (empty($name)) return "Nienazwana_Galeria";
        $name = trim((string)$name);
        $name = preg_replace("/[<>:\"\/\\\\|?*\\x00-\\x1F\\t\\n\\r\\f\\v]/", "_", $name);
        $name = preg_replace("/\\s+/", " ", $name);
        $name = trim($name);
        if (strlen($name) > 1) {
            $name = preg_replace("/_+/", "_", $name);
            $name = preg_replace("/-+/", "-", $name);
        }
        $name = trim($name, " _-.");
        if (mb_strlen($name) > 150) {
            $name = mb_substr($name, 0, 150);
            $name = trim($name, " _-.");
        }
        return empty($name) ? "Nienazwana_Galeria" : $name;
    }
    
    public static function getGalleryIdFromUrl($url) {
        if (empty($url) || !is_string($url)) {
            return "error_invalid_url_" . time();
        }
        try {
            $path = parse_url($url, PHP_URL_PATH);
            $segments = explode("/", trim($path, "/"));
            $gallery_id_str = urldecode(end($segments));
            $gallery_id_str = explode(".", $gallery_id_str)[0];
            return empty($gallery_id_str) ? "error_empty_id_" . time() : $gallery_id_str;
        } catch (Exception $e) {
            return "error_parsing_id_" . time();
        }
    }
}