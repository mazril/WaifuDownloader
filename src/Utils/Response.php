<?php
namespace App\\Utils;

class Response {
    public static function json($data, $statusCode = 200) {
        http_response_code($statusCode);
        header("Content-Type: application/json");
        echo json_encode($data);
        exit;
    }
    
    public static function error($message, $statusCode = 400) {
        self::json(["success" => false, "message" => $message], $statusCode);
    }
    
    public static function success($data = [], $message = null) {
        $response = ["success" => true];
        if ($message) $response["message"] = $message;
        if ($data) $response = array_merge($response, $data);
        self::json($response);
    }
}