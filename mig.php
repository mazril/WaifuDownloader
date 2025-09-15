<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <title>Migracja WaifuDownloader</title>
    <style>
        body { font-family: monospace; padding: 20px; background: #1e1e1e; color: #0f0; }
        pre { background: #000; padding: 10px; border: 1px solid #0f0; overflow-x: auto; }
        .success { color: #0f0; }
        .error { color: #f00; }
        .warning { color: #ff0; }
        button { background: #0f0; color: #000; padding: 10px 20px; border: none; cursor: pointer; font-weight: bold; }
        button:hover { background: #0a0; }
        #log { max-height: 400px; overflow-y: auto; }
    </style>
</head>
<body>
    <h1>🚀 Migracja WaifuDownloader do Nowej Struktury</h1>
    <p>Ten skrypt utworzy całą nową strukturę projektu zgodnie z planem migracji.</p>
    
    <button onclick="runMigration()">▶️ URUCHOM MIGRACJĘ</button>
    <button onclick="downloadScript()">💾 POBIERZ SKRYPT PHP</button>
    
    <div id="log"></div>

    <script>
        function log(msg, type = 'info') {
            const logDiv = document.getElementById('log');
            const entry = document.createElement('div');
            entry.className = type;
            entry.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
            logDiv.appendChild(entry);
            logDiv.scrollTop = logDiv.scrollHeight;
        }

        function runMigration() {
            log('Rozpoczynam migrację...', 'success');
            log('Zapisz poniższy skrypt jako migrate.php w katalogu głównym projektu i uruchom: php migrate.php', 'warning');
            
            // Pokaż kod skryptu
            const scriptContent = getMigrationScript();
            const pre = document.createElement('pre');
            pre.textContent = scriptContent;
            document.getElementById('log').appendChild(pre);
        }

        function downloadScript() {
            const scriptContent = getMigrationScript();
            const blob = new Blob([scriptContent], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'migrate.php';
            a.click();
            URL.revokeObjectURL(url);
            log('Skrypt pobrany jako migrate.php', 'success');
        }

        function getMigrationScript() {
            return `<?php
/**
 * Skrypt migracji WaifuDownloader
 * Uruchom: php migrate.php
 */

set_time_limit(0);
error_reporting(E_ALL);
ini_set('display_errors', 1);

class WaifuMigration {
    private $baseDir;
    private $log = [];
    
    public function __construct() {
        $this->baseDir = __DIR__;
        echo "\\n=== MIGRACJA WAIFUDOWNLOADER ===\\n\\n";
    }
    
    public function run() {
        try {
            $this->backup();
            $this->createDirectoryStructure();
            $this->createConfigFiles();
            $this->createUtilsFiles();
            $this->createRepositoryFiles();
            $this->createServiceFiles();
            $this->createControllerFiles();
            $this->createPublicFiles();
            $this->createTemplateFiles();
            $this->createJavaScriptFiles();
            $this->showSummary();
        } catch (Exception $e) {
            echo "❌ BŁĄD: " . $e->getMessage() . "\\n";
            exit(1);
        }
    }
    
    private function backup() {
        echo "📦 Tworzenie backupu...\\n";
        $backupDir = $this->baseDir . '/backup_' . date('Y-m-d_H-i-s');
        if (!mkdir($backupDir, 0755, true)) {
            throw new Exception("Nie można utworzyć katalogu backup");
        }
        
        // Kopiuj ważne pliki
        $filesToBackup = ['index.php', 'api.php', 'php_utils.php', 'php_config.php', 'php_db_config.php', 'styles.css'];
        foreach ($filesToBackup as $file) {
            if (file_exists($this->baseDir . '/' . $file)) {
                copy($this->baseDir . '/' . $file, $backupDir . '/' . $file);
            }
        }
        echo "✅ Backup utworzony w: $backupDir\\n\\n";
    }
    
    private function createDirectoryStructure() {
        echo "📁 Tworzenie struktury katalogów...\\n";
        
        $dirs = [
            'src/Controllers',
            'src/Services',
            'src/Database/Models',
            'src/Database/Repositories',
            'src/Utils',
            'src/Templates/tabs',
            'src/Templates/components',
            'src/Templates/modals',
            'public/assets/css',
            'public/assets/js/components',
            'public/assets/js/utils',
            'config',
            'storage/logs',
            'storage/cache'
        ];
        
        foreach ($dirs as $dir) {
            $path = $this->baseDir . '/' . $dir;
            if (!is_dir($path)) {
                mkdir($path, 0755, true);
                echo "  ✅ $dir\\n";
            }
        }
        echo "\\n";
    }
    
    private function createConfigFiles() {
        echo "⚙️ Tworzenie plików konfiguracyjnych...\\n";
        
        // config/app.php
        $this->writeFile('config/app.php', '<?php
return [
    "app_name" => "WaifuDownloader",
    "version" => "2.0.0",
    "debug" => true,
    "timezone" => "Europe/Warsaw",
    "base_data_dir" => "Modelki",
    "api_url" => "api.php"
];');
        
        // config/database.php
        $this->writeFile('config/database.php', '<?php
return [
    "host" => DB_HOST ?? "localhost",
    "user" => DB_USER ?? "waifudownloader",
    "password" => DB_PASS ?? "vfdsc34Ffgaa307",
    "database" => DB_NAME ?? "waifudownloader",
    "port" => DB_PORT ?? 3306,
    "charset" => "utf8mb4"
];');
        
        // config/routes.php
        $this->writeFile('config/routes.php', '<?php
return [
    // Status
    "get_status" => ["controller" => "StatusController", "method" => "getCurrentStatus"],
    "clear_cache" => ["controller" => "StatusController", "method" => "clearCache"],
    
    // Models
    "get_models_list" => ["controller" => "ModelController", "method" => "getModelsList"],
    "add_model" => ["controller" => "ModelController", "method" => "addModel"],
    "get_galleries_for_model" => ["controller" => "ModelController", "method" => "getGalleriesForModel"],
    
    // Galleries
    "get_gallery_files" => ["controller" => "GalleryController", "method" => "getGalleryFiles"],
    "rename_gallery_folder" => ["controller" => "GalleryController", "method" => "renameGalleryFolder"],
    "mark_gallery_completed" => ["controller" => "GalleryController", "method" => "markGalleryCompleted"],
    "toggle_gallery_disabled_status" => ["controller" => "GalleryController", "method" => "toggleGalleryDisabled"],
    "search_galleries" => ["controller" => "GalleryController", "method" => "searchGalleries"],
    
    // Queue
    "get_queue" => ["controller" => "QueueController", "method" => "getQueue"],
    "update_queue" => ["controller" => "QueueController", "method" => "updateQueue"],
    "prioritize" => ["controller" => "QueueController", "method" => "addToQueue"],
    
    // AI
    "get_galleries_for_ai_test" => ["controller" => "AIController", "method" => "getGalleriesForTest"],
    "trigger_ai_test_run" => ["controller" => "AIController", "method" => "triggerTestRun"],
    "trigger_ai_update" => ["controller" => "AIController", "method" => "triggerUpdate"],
    "get_ai_prompt_configs" => ["controller" => "AIController", "method" => "getPromptConfigs"],
    "save_ai_prompt_config" => ["controller" => "AIController", "method" => "savePromptConfig"],
    "get_global_ai_settings" => ["controller" => "AIController", "method" => "getGlobalSettings"],
    "save_global_ai_settings" => ["controller" => "AIController", "method" => "saveGlobalSettings"],
    "promote_test_to_production" => ["controller" => "AIController", "method" => "promoteTestToProd"],
    
    // Refresh
    "refresh_empty_descriptions_all" => ["controller" => "ModelController", "method" => "refreshEmptyDescriptions"],
    "refresh_all_galleries_lists" => ["controller" => "ModelController", "method" => "refreshAllGalleries"]
];');
    }
    
    private function createUtilsFiles() {
        echo "🛠️ Tworzenie plików Utils...\\n";
        
        // src/Utils/Response.php
        $this->writeFile('src/Utils/Response.php', '<?php
namespace App\\\\Utils;

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
}');

        // src/Utils/Sanitizer.php
        $this->writeFile('src/Utils/Sanitizer.php', '<?php
namespace App\\\\Utils;

class Sanitizer {
    public static function sanitizeFoldername($name) {
        if (empty($name)) return "Nienazwana_Galeria";
        $name = trim((string)$name);
        $name = preg_replace("/[<>:\"\\/\\\\\\\\|?*\\\\x00-\\\\x1F\\\\t\\\\n\\\\r\\\\f\\\\v]/", "_", $name);
        $name = preg_replace("/\\\\s+/", " ", $name);
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
}');

        // src/Utils/Logger.php
        $this->writeFile('src/Utils/Logger.php', '<?php
namespace App\\\\Utils;

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
        
        $entry = "[$timestamp] [Client: $remote] [$method $uri] $message\\n";
        file_put_contents(self::$logFile, $entry, FILE_APPEND);
    }
}');
    }
    
    private function createRepositoryFiles() {
        echo "💾 Tworzenie plików Repository...\\n";
        
        // src/Database/Connection.php
        $this->writeFile('src/Database/Connection.php', '<?php
namespace App\\\\Database;

use PDO;
use PDOException;

class Connection {
    private static $pdo = null;
    
    public static function getInstance() {
        if (self::$pdo === null) {
            $config = require __DIR__ . "/../../config/database.php";
            
            $dsn = "mysql:host={$config["host"]};port={$config["port"]};dbname={$config["database"]};charset={$config["charset"]}";
            $options = [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES => false,
            ];
            
            try {
                self::$pdo = new PDO($dsn, $config["user"], $config["password"], $options);
            } catch (PDOException $e) {
                error_log("Database connection error: " . $e->getMessage());
                return null;
            }
        }
        return self::$pdo;
    }
}');

        // src/Database/Repositories/BaseRepository.php
        $this->writeFile('src/Database/Repositories/BaseRepository.php', '<?php
namespace App\\\\Database\\\\Repositories;

use App\\\\Database\\\\Connection;
use PDO;

abstract class BaseRepository {
    protected $pdo;
    protected $table;
    
    public function __construct() {
        $this->pdo = Connection::getInstance();
    }
    
    protected function query($sql, $params = []) {
        $stmt = $this->pdo->prepare($sql);
        $stmt->execute($params);
        return $stmt;
    }
    
    protected function fetchOne($sql, $params = []) {
        return $this->query($sql, $params)->fetch();
    }
    
    protected function fetchAll($sql, $params = []) {
        return $this->query($sql, $params)->fetchAll();
    }
    
    protected function execute($sql, $params = []) {
        return $this->query($sql, $params)->rowCount();
    }
}');

        // Dodatkowe repozytoria...
        $this->createRepositoryFile('ModelRepository');
        $this->createRepositoryFile('GalleryRepository');
        $this->createRepositoryFile('QueueRepository');
        $this->createRepositoryFile('AppStateRepository');
    }
    
    private function createRepositoryFile($name) {
        $content = '<?php
namespace App\\\\Database\\\\Repositories;

class ' . $name . ' extends BaseRepository {
    // Implementacja metod specyficznych dla ' . $name . '
}';
        $this->writeFile("src/Database/Repositories/{$name}.php", $content);
    }
    
    private function createServiceFiles() {
        echo "🔧 Tworzenie plików Service...\\n";
        
        $services = ['ModelService', 'GalleryService', 'QueueService', 'AIService', 'CacheService'];
        
        foreach ($services as $service) {
            $this->writeFile("src/Services/{$service}.php", '<?php
namespace App\\\\Services;

class ' . $service . ' {
    // Implementacja logiki biznesowej dla ' . $service . '
}');
        }
    }
    
    private function createControllerFiles() {
        echo "🎮 Tworzenie plików Controller...\\n";
        
        $controllers = ['StatusController', 'ModelController', 'GalleryController', 'QueueController', 'AIController'];
        
        foreach ($controllers as $controller) {
            $this->writeFile("src/Controllers/{$controller}.php", '<?php
namespace App\\\\Controllers;

use App\\\\Utils\\\\Response;

class ' . $controller . ' {
    // Implementacja metod kontrolera
}');
        }
    }
    
    private function createPublicFiles() {
        echo "🌐 Tworzenie plików publicznych...\\n";
        
        // public/index.php
        $this->writeFile('public/index.php', '<?php
require_once __DIR__ . "/../src/Templates/layout.php";');
        
        // public/api.php
        $this->writeFile('public/api.php', '<?php
require_once __DIR__ . "/../vendor/autoload.php";

use App\\\\Utils\\\\Response;
use App\\\\Utils\\\\Logger;

header("Content-Type: application/json");
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type");

if ($_SERVER["REQUEST_METHOD"] == "OPTIONS") {
    http_response_code(200);
    exit();
}

$routes = require __DIR__ . "/../config/routes.php";
$action = $_GET["action"] ?? $_POST["action"] ?? null;

if (!$action || !isset($routes[$action])) {
    Response::error("Unknown action", 400);
}

$route = $routes[$action];
$controllerClass = "App\\\\\\\\Controllers\\\\\\\\" . $route["controller"];
$method = $route["method"];

if (!class_exists($controllerClass)) {
    Response::error("Controller not found", 500);
}

$controller = new $controllerClass();
if (!method_exists($controller, $method)) {
    Response::error("Method not found", 500);
}

try {
    Logger::log("Executing: {$route["controller"]}::{$method}");
    $controller->$method();
} catch (Exception $e) {
    Logger::log("Error: " . $e->getMessage());
    Response::error("Internal server error", 500);
}');
        
        // Przenieś style
        if (file_exists($this->baseDir . '/styles.css')) {
            copy($this->baseDir . '/styles.css', $this->baseDir . '/public/assets/css/main.css');
        }
    }
    
    private function createTemplateFiles() {
        echo "📄 Tworzenie szablonów...\\n";
        
        // src/Templates/layout.php
        $this->writeFile('src/Templates/layout.php', '<!DOCTYPE html>
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
</html>');
        
        // Komponenty i zakładki
        $this->writeFile('src/Templates/components/navigation.php', '<!-- Navigation component -->');
        $this->writeFile('src/Templates/tabs/status-galleries.php', '<!-- Status galleries tab -->');
        $this->writeFile('src/Templates/tabs/test-ai-titles.php', '<!-- Test AI tab -->');
        $this->writeFile('src/Templates/tabs/ollama-settings.php', '<!-- Settings tab -->');
        
        // Modale
        $this->writeFile('src/Templates/modals/queue-modal.php', '<!-- Queue modal -->');
        $this->writeFile('src/Templates/modals/image-viewer.php', '<!-- Image viewer modal -->');
        $this->writeFile('src/Templates/modals/search-modal.php', '<!-- Search modal -->');
        $this->writeFile('src/Templates/modals/lightbox.php', '<!-- Lightbox modal -->');
    }
    
    private function createJavaScriptFiles() {
        echo "📜 Tworzenie plików JavaScript...\\n";
        
        // public/assets/js/app.js
        $this->writeFile('public/assets/js/app.js', '// Main application JavaScript
class App {
    constructor() {
        this.initTabs();
        this.initEventListeners();
    }
    
    initTabs() {
        // Tab initialization logic
    }
    
    initEventListeners() {
        // Event listeners setup
    }
}

document.addEventListener("DOMContentLoaded", () => {
    new App();
});');
        
        // Utils
        $this->writeFile('public/assets/js/utils/api.js', '// API wrapper
const API = {
    baseUrl: "/api.php",
    
    async request(action, params = {}, method = "GET") {
        // API request implementation
    }
};');
        
        $this->writeFile('public/assets/js/utils/ui.js', '// UI utilities
const UI = {
    showToast(message, isError = false) {
        // Toast implementation
    }
};');
        
        // Components
        $this->writeFile('public/assets/js/components/StatusTab.js', '// Status tab component');
        $this->writeFile('public/assets/js/components/TestAITab.js', '// Test AI tab component');
        $this->writeFile('public/assets/js/components/SettingsTab.js', '// Settings tab component');
    }
    
    private function writeFile($path, $content) {
        $fullPath = $this->baseDir . '/' . $path;
        if (file_put_contents($fullPath, $content)) {
            echo "  ✅ $path\\n";
            $this->log[] = "Created: $path";
        } else {
            throw new Exception("Cannot write file: $path");
        }
    }
    
    private function showSummary() {
        echo "\\n" . str_repeat("=", 50) . "\\n";
        echo "✅ MIGRACJA ZAKOŃCZONA POMYŚLNIE!\\n";
        echo str_repeat("=", 50) . "\\n\\n";
        
        echo "📋 KOLEJNE KROKI:\\n";
        echo "1. Zainstaluj Composer: composer init && composer install\\n";
        echo "2. Skonfiguruj autoloader w composer.json\\n";
        echo "3. Zaktualizuj .htaccess dla nowego routingu\\n";
        echo "4. Przetestuj każdą funkcjonalność\\n";
        echo "5. Usuń stare pliki po pomyślnych testach\\n\\n";
        
        echo "📁 Utworzono " . count($this->log) . " plików\\n";
        echo "📦 Backup starych plików znajduje się w katalogu backup_*\\n\\n";
        
        echo "⚠️ WAŻNE:\\n";
        echo "- Sprawdź konfigurację bazy danych w config/database.php\\n";
        echo "- Zaktualizuj ścieżki w plikach JavaScript\\n";
        echo "- Przetestuj wszystkie endpointy API\\n";
    }
}

// Uruchom migrację
$migration = new WaifuMigration();
$migration->run();
?>`;
        }
    </script>
</body>
</html>