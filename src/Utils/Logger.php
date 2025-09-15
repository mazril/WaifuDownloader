<?php
namespace App\\Utils;

class Logger {
    private static $logFile;
    
    public static function init() {
        self::$logFile = __DIR__ . "/../../storage/logs/api_debug.txt";
    }
    
    public static function log($message) {
        if (!self::$logFile) self::init();
        $timestamp = date("Y-m-d H:i:s");
        $remote = $_SERVER["REMOTE_ADDR"] ?? "UNKNOWN";
        $method = $_SERVER["REQUEST_METHOD"] ?? "UNKNOWN";
        $uri = $_SERVER["REQUEST_URI"] ?? "UNKNOWN";
        
        $entry = "[$timestamp] [Client: $remote] [$method $uri] $message\n";
        file_put_contents(self::$logFile, $entry, FILE_APPEND);
    }
}