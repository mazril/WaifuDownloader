<?php
require_once __DIR__ . "/../vendor/autoload.php";

use App\\Utils\\Response;
use App\\Utils\\Logger;

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
$controllerClass = "App\\\\Controllers\\\\" . $route["controller"];
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
}