<?php
if (!function_exists('api_log')) {
    function api_log(string $level, string $message, array $context = []): void {
        $root = dirname(__DIR__, 3);
        $logDir = $root . '/logs';
        if (!is_dir($logDir)) { @mkdir($logDir, 0777, true); }
        $line = [
            'ts' => date('c'),
            'level' => $level,
            'message' => $message,
            'context' => $context,
            'ip' => $_SERVER['REMOTE_ADDR'] ?? null,
            'ua' => $_SERVER['HTTP_USER_AGENT'] ?? null,
        ];
        @file_put_contents($logDir . '/app.log', json_encode($line, JSON_UNESCAPED_UNICODE) . PHP_EOL, FILE_APPEND);
    }
}
