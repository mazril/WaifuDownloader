<?php
// Intentionally trigger a warning to test JSON error wrapping
$undefined += 1;
echo json_encode(['ok'=>true,'after'=>true]);
