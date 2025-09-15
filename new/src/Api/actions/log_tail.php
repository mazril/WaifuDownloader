<?php
$root = dirname(__DIR__, 3);
$log = $root . '/logs/app.log';
$max = isset($_GET['n']) ? max(10, min(2000, (int)$_GET['n'])) : 200;
$lines = [];
if (is_file($log)) {
    $size = filesize($log);
    if ($size <= 1024*1024) {
        $buf = file_get_contents($log);
    } else {
        $fp = fopen($log, 'r'); fseek($fp, $size - 1024*1024); $buf = stream_get_contents($fp); fclose($fp);
    }
    $all = explode("\n", $buf);
    $lines = array_slice(array_filter($all), -$max);
}
echo json_encode(['ok'=>true, 'lines'=>$lines]);
