<?php
$info = [
  'script_name' => $_SERVER['SCRIPT_NAME'] ?? null,
  'request_uri' => $_SERVER['REQUEST_URI'] ?? null,
  'base_path_hint' => rtrim(dirname($_SERVER['SCRIPT_NAME'] ?? ''), '/\\'),
  'server' => [
    'software' => $_SERVER['SERVER_SOFTWARE'] ?? null,
    'addr' => $_SERVER['SERVER_ADDR'] ?? null,
    'port' => $_SERVER['SERVER_PORT'] ?? null,
  ],
  'php' => PHP_VERSION,
  'get' => $_GET,
  'post' => $_POST,
];
echo json_encode(['ok'=>true,'diagnostics'=>$info]);
