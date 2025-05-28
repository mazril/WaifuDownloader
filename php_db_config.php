<?php
// php_db_config.php

// Wypełnij swoimi danymi dostępowymi do bazy danych MySQL
define('DB_HOST', 'localhost');
define('DB_USER', 'twoj_uzytkownik');
define('DB_PASS', 'twoje_haslo');
define('DB_NAME', 'waifudownloader');
define('DB_PORT', 3306); // Domyślny port MySQL

/**
 * Tworzy i zwraca obiekt połączenia PDO.
 * @return PDO|null Połączenie PDO lub null w przypadku błędu.
 */
function get_db_connection() {
    static $pdo = null;

    if ($pdo === null) {
        $dsn = "mysql:host=" . DB_HOST . ";port=" . DB_PORT . ";dbname=" . DB_NAME . ";charset=utf8mb4";
        $options = [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
        ];
        try {
            $pdo = new PDO($dsn, DB_USER, DB_PASS, $options);
        } catch (\PDOException $e) {
            error_log("Błąd połączenia z bazą danych: " . $e->getMessage());
            // W środowisku produkcyjnym można zwrócić bardziej ogólny błąd
            // http_response_code(500);
            // echo json_encode(['success' => false, 'message' => 'Błąd serwera - nie można połączyć z bazą danych.']);
            // exit();
            return null; // Zwróć null, aby obsłużyć błąd w kodzie wywołującym
        }
    }
    return $pdo;
}
?>