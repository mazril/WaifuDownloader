<?php
// Base path for assets (e.g., /new/public)
$basePath = rtrim(dirname($_SERVER['SCRIPT_NAME'] ?? ''), '/\\');
?>
<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Panel</title>
  <link rel="stylesheet" href="<?=$basePath?>/assets/css/styles.css?v=<?=time()?>">
</head>
<body>
  <!-- Twój dotychczasowy HTML zostaje bez zmian; ważna jest kolejność skryptów poniżej -->
  <div id="app-root"><!-- istniejąca zawartość strony --></div>

  <!-- runtime definiuje __API_URL__ i patchuje fetch/XHR -->
  <script src="<?=$basePath?>/assets/js/runtime.js"></script>
  <!-- app.js: Twój przeniesiony kod JS (inline z dawnego index.php) -->
  <script src="<?=$basePath?>/assets/js/app.js"></script>
</body>
</html>
