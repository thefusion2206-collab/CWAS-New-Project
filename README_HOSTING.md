# AccessGuard — Login + MySQL + GitHub + Railway

## What this version includes

- Login page as the first page
- User registration
- Password hashing
- Successful login tracking in MySQL
- Scan history linked to logged-in user
- Login Records page
- Flask backend
- Selenium + Axe accessibility scanning
- Dockerfile with Chromium for cloud deployment
- Railway configuration
- Local MySQL fallback
- Production Gunicorn server

## 1. LOCAL RUN

Open this folder in VS Code.

Create virtual environment:
    python -m venv venv

Windows activation:
    venv\Scripts\activate

Install:
    python -m pip install -r requirements.txt

Make sure MySQL Server is running.

Open app.py and for local use either:
- set MYSQLPASSWORD in your environment, OR
- replace YOUR_MYSQL_PASSWORD in the fallback value temporarily.

Run:
    python app.py

Open:
    http://127.0.0.1:5000

The app automatically creates the database and required tables locally.

## 2. GITHUB

Do NOT upload:
- venv/
- .env
- real passwords

Create a GitHub repository, then:

    git init
    git add .
    git commit -m "AccessGuard hosting ready"
    git branch -M main
    git remote add origin YOUR_REPOSITORY_URL
    git push -u origin main

## 3. RAILWAY

1. Create a Railway account.
2. Create a new project.
3. Deploy the GitHub repository.
4. Add a MySQL service.
5. Make sure the web service can access the MySQL service.
6. Railway provides MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD and MYSQLDATABASE.
7. The application reads those variables automatically.
8. The Dockerfile installs Chromium and Chrome driver for Selenium.
9. Generate a public domain in Railway.
10. Open the generated HTTPS URL.

## 4. RAILWAY VARIABLES

You normally do not need to manually type the MySQL values if Railway exposes them to the service.

If variables are not automatically available, create references to the MySQL service variables:
    MYSQLHOST
    MYSQLPORT
    MYSQLUSER
    MYSQLPASSWORD
    MYSQLDATABASE

Do not put these secrets in GitHub.

## 5. DATABASE

On first startup, gunicorn.conf.py calls init_db(), which creates:
    users
    login_history
    scans_new

The local database is:
    accessibility_scanner_new

On Railway, the database name is read from MYSQLDATABASE.

## 6. TESTING

Open:
    https://YOUR-RAILWAY-DOMAIN/health

Expected:
    {"status":"ok","service":"AccessGuard"}

Then:
    /login

Register -> Login -> Scan -> check Login Records and Scan History.

## IMPORTANT

The project is intended for a college/demo deployment. Do not use the example secret key or weak passwords for a real public production system. For a public deployment, set a strong SECRET_KEY environment variable and update app.py to read it.
