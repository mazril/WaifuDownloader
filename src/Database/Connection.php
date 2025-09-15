<?php
namespace App\\Database;

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
}