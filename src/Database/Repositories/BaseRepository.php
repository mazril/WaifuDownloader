<?php
namespace App\\Database\\Repositories;

use App\\Database\\Connection;
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
}