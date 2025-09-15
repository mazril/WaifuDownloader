<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Panel Główny WaifuDownloader</title>
    <link rel="stylesheet" href="assets/css/main.css">
</head>
<body>
    <div class="global-container">
        <?php include __DIR__ . "/components/navigation.php"; ?>
        <div class="tab-content-wrapper">
            <?php include __DIR__ . "/tabs/status-galleries.php"; ?>
            <?php include __DIR__ . "/tabs/test-ai-titles.php"; ?>
            <?php include __DIR__ . "/tabs/ollama-settings.php"; ?>
        </div>
    </div>
    <?php include __DIR__ . "/modals/queue-modal.php"; ?>
    <?php include __DIR__ . "/modals/image-viewer.php"; ?>
    <?php include __DIR__ . "/modals/search-modal.php"; ?>
    <?php include __DIR__ . "/modals/lightbox.php"; ?>
    
    <script src="assets/js/utils/api.js"></script>
    <script src="assets/js/utils/ui.js"></script>
    <script src="assets/js/components/StatusTab.js"></script>
    <script src="assets/js/components/TestAITab.js"></script>
    <script src="assets/js/components/SettingsTab.js"></script>
    <script src="assets/js/app.js"></script>
</body>
</html>