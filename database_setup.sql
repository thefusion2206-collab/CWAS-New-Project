CREATE DATABASE IF NOT EXISTS accessibility_scanner_new;
USE accessibility_scanner_new;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL,
    last_login DATETIME NULL
);

CREATE TABLE IF NOT EXISTS login_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    username VARCHAR(100) NOT NULL,
    login_time DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_login_user (user_id),
    INDEX idx_login_time (login_time)
);

CREATE TABLE IF NOT EXISTS scans_new (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    username VARCHAR(100) NULL,
    url VARCHAR(1000) NOT NULL,
    title VARCHAR(500),
    score INT,
    total_tests INT,
    passed_tests INT,
    failed_tests INT,
    incomplete_tests INT,
    violations_json LONGTEXT,
    passes_json LONGTEXT,
    incomplete_json LONGTEXT,
    scan_time DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_scan_user (user_id),
    INDEX idx_scan_time (scan_time)
);

SELECT * FROM users;
SELECT * FROM login_history;
SELECT * FROM scans_new;
