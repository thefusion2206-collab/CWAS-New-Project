AccessGuard - Local MySQL User Tracking Version

This version is intended to run locally on your laptop.
NO GitHub hosting is required.

What is stored in MySQL:
1. users
   - Every registered account
   - username
   - password_hash
   - created_at
   - last_login

2. login_history
   - Every successful login
   - user_id
   - username
   - login_time

3. scans_new
   - Every successful scan
   - user_id of the logged-in account
   - username
   - scanned URL
   - score/results
   - scan time

Important behavior:
- User A logs in -> the login is saved in login_history with User A's user_id.
- User A scans a website -> the scan is saved in scans_new with User A's user_id.
- User B logs in and scans -> B's records are stored separately.
- The website's Scan History page shows only the currently logged-in user's scans.
- MySQL Workbench can show ALL users, ALL login records and ALL scan records.

LOCAL SETUP:
1. Install Python 3.13 (64-bit).
2. Install MySQL Server + MySQL Workbench.
3. Open this folder in VS Code.
4. Open Terminal.
5. Run:
   python -m pip install -r requirements.txt
6. Start MySQL Server.
7. Open app.py and replace YOUR_MYSQL_PASSWORD with your MySQL root password.
8. Run:
   python app.py
9. Open:
   http://127.0.0.1:5000
10. Register an account.
11. Login.
12. Scan a website.
13. Open Scan History to see that account's scans.

MYSQL WORKBENCH:
Run:
USE accessibility_scanner_new;

SELECT * FROM users;
SELECT * FROM login_history;
SELECT * FROM scans_new;

To see one user's scans:
SELECT * FROM scans_new
WHERE user_id = 1
ORDER BY id DESC;

To see one user's login records:
SELECT * FROM login_history
WHERE user_id = 1
ORDER BY id DESC;

To join user name with scans:
SELECT s.id, u.username, s.url, s.score, s.scan_time
FROM scans_new s
JOIN users u ON s.user_id = u.id
ORDER BY s.id DESC;

To join user name with login history:
SELECT l.id, u.username, l.login_time
FROM login_history l
JOIN users u ON l.user_id = u.id
ORDER BY l.id DESC;

The application automatically creates the database/tables when run locally.
Chrome/Chromium is required because Selenium performs the website scan.
