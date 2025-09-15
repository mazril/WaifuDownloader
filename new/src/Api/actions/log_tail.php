<?php
$root = dirname(__DIR__, 3);
$log = $root . '/logs/app.log';
$max = isset($_GET['n']) ? max(10, min(2000, (int)$_GET['n'])) : 200;
$lines = [];
if (is_file($log)) {
    $fh = fopen($log, 'r');
    if ($fh) {
        // naive tail: read entire file if small, else last ~1MB
        $size = filesize($log);
        $seek = max(0, $size - 1024*1024);
        fseek($fh, $seek);
        $buf = stream_get_contents($fh);
        fclose($fh);
        $all = explode("\n", $buf);
        $lines = array_slice(array_filter($all), -$max);
    }
}
echo json_encode(['ok'=>true, 'lines'=>$lines]);
