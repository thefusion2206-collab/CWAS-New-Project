import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from datetime import datetime
from urllib.parse import urlparse
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json, csv, io, ipaddress, socket, secrets, math
from collections import Counter
from flask import Response, abort
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from axe_selenium_python import Axe

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "accessguard-local-dev-key")

DB_CONFIG = {
    "host": os.environ.get("MYSQLHOST", "localhost"),
    "user": os.environ.get("MYSQLUSER", "root"),
    "password": os.environ.get("MYSQLPASSWORD", "YOUR_MYSQL_PASSWORD"),
    "database": os.environ.get("MYSQLDATABASE", "accessibility_scanner_new"),
    "port": int(os.environ.get("MYSQLPORT", "3306"))
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def init_db():
    # On Railway, the MySQL database is already created.
    # Locally, create the configured database if possible.
    if os.environ.get("MYSQLHOST"):
        conn = get_db_connection()
    else:
        cfg = DB_CONFIG.copy()
        db_name = cfg.pop("database")
        conn = mysql.connector.connect(**cfg)
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
        cur.close()
        conn.close()
        conn = get_db_connection()

    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            created_at DATETIME NOT NULL,
            last_login DATETIME NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS login_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            username VARCHAR(100) NOT NULL,
            login_time DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_login_user (user_id),
            INDEX idx_login_time (login_time)
        )
    """)

    cur.execute("""
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
        )
    """)

    # Add columns when upgrading an older local database.
    for sql in [
        "ALTER TABLE scans_new ADD COLUMN user_id INT NULL",
        "ALTER TABLE scans_new ADD COLUMN username VARCHAR(100) NULL"
    ]:
        try:
            cur.execute(sql)
        except mysql.connector.Error:
            pass

    conn.commit()
    cur.close()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def clean_url(url):
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url

def make_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--log-level=3")

    # Railway/Docker commonly uses Chromium. Selenium Manager
    # will locate/download a compatible driver when needed.
    chrome_binary = os.environ.get("CHROME_BIN")
    if chrome_binary:
        options.binary_location = chrome_binary

    return webdriver.Chrome(options=options)

def simplify(item):
    return {
        "id": item.get("id", ""),
        "impact": item.get("impact") or "minor",
        "help": item.get("help", "Accessibility issue"),
        "description": item.get("description", ""),
        "helpUrl": item.get("helpUrl", ""),
        "tags": item.get("tags", []),
        "nodes": [
            {
                "html": n.get("html", ""),
                "target": n.get("target", []),
                "failureSummary": n.get("failureSummary", "")
            } for n in item.get("nodes", [])
        ]
    }

def scan_website(url):
    driver = make_driver()
    try:
        driver.get(url)
        axe = Axe(driver)
        axe.inject()
        results = axe.run()

        violations = [simplify(x) for x in results.get("violations", [])]
        passes = [simplify(x) for x in results.get("passes", [])]
        incomplete = [simplify(x) for x in results.get("incomplete", [])]

        total = len(violations) + len(passes) + len(incomplete)
        score = round((len(passes) / total) * 100) if total else 0

        return {
            "url": url, "title": driver.title or "Untitled page",
            "score": score, "total": total,
            "passed": len(passes), "failed": len(violations),
            "incomplete": len(incomplete),
            "violations": violations, "passes": passes,
            "incomplete_results": incomplete
        }
    finally:
        driver.quit()

def save_scan(data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO scans_new
        (user_id, username, url, title, score, total_tests, passed_tests,
         failed_tests, incomplete_tests, violations_json, passes_json,
         incomplete_json, scan_time)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        session["user_id"], session["username"], data["url"], data["title"],
        data["score"], data["total"], data["passed"], data["failed"],
        data["incomplete"], json.dumps(data["violations"]),
        json.dumps(data["passes"]), json.dumps(data["incomplete_results"]),
        datetime.now()
    ))
    new_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    return new_id


# ---------------------------------------------------------------- security
@app.before_request
def csrf_protect():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        if not secrets.compare_digest(sent, session["csrf"]):
            abort(400, "Invalid CSRF token. Refresh the page and try again.")

@app.context_processor
def inject_csrf():
    return {"csrf_token": session.get("csrf", "")}

def check_target(url):
    """Block scans of private/internal addresses when the app is hosted (SSRF guard)."""
    host = urlparse(url).hostname
    if not host:
        raise ValueError("Please enter a valid website URL.")
    if not os.environ.get("MYSQLHOST"):      # local run: anything allowed
        return
    try:
        ips = {a[4][0].split("%")[0] for a in socket.getaddrinfo(host, None)}
    except socket.gaierror:
        raise ValueError("Could not resolve this website address.")
    for ip in ips:
        a = ipaddress.ip_address(ip)
        if a.is_private or a.is_loopback or a.is_link_local or a.is_reserved:
            raise ValueError("Scanning private or internal addresses is not allowed.")

# ---------------------------------------------------------------- analytics
WEIGHT = {"critical": 10, "serious": 6, "moderate": 3, "minor": 1}

def grade_for(n):
    for g, lo in (("A", 90), ("B", 75), ("C", 60), ("D", 40)):
        if n >= lo:
            return g
    return "F"

def analyze(d):
    """Derive severity, WCAG-level, category, quick-win and grade data from one scan."""
    v = d["violations"]
    sev = {k: 0 for k in WEIGHT}
    for x in v:
        sev[x["impact"] if x["impact"] in sev else "minor"] += 1

    penalty = sum(WEIGHT.get(x["impact"], 1) * min(max(len(x["nodes"]), 1), 3) for x in v)
    weighted = max(0, 100 - penalty)

    cats = {}
    for kind, items in (("fail", v), ("pass", d["passes"])):
        for x in items:
            for t in x["tags"]:
                if t.startswith("cat."):
                    c = cats.setdefault(t[4:].replace("-", " ").title(), {"fail": 0, "pass": 0})
                    c[kind] += 1
    cat_rows = sorted(({"name": k, **c, "total": c["fail"] + c["pass"]} for k, c in cats.items()),
                      key=lambda r: (-r["fail"], -r["total"]))

    levels = {}
    label = {"wcag2a": "WCAG 2.0 A", "wcag2aa": "WCAG 2.0 AA", "wcag21a": "WCAG 2.1 A",
             "wcag21aa": "WCAG 2.1 AA", "wcag22aa": "WCAG 2.2 AA", "best-practice": "Best Practice"}
    for kind, items in (("fail", v), ("pass", d["passes"])):
        for x in items:
            for t in x["tags"]:
                if t in label:
                    levels.setdefault(label[t], {"fail": 0, "pass": 0})[kind] += 1

    quick = sorted(v, key=lambda x: WEIGHT.get(x["impact"], 1) * max(len(x["nodes"]), 1), reverse=True)[:5]
    elements = sum(len(x["nodes"]) for x in v)
    risk = "Critical" if sev["critical"] else "High" if sev["serious"] else "Medium" if sev["moderate"] else "Low" if sev["minor"] else "None"
    return {"sev": sev, "weighted": weighted, "grade": grade_for(weighted), "cats": cat_rows,
            "levels": levels, "quick": quick, "elements": elements, "risk": risk,
            "sev_max": max(list(sev.values()) + [1])}

def load_scan(scan_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM scans_new WHERE id = %s AND user_id = %s", (scan_id, session["user_id"]))
    r = cur.fetchone()
    cur.close()
    conn.close()
    if not r:
        abort(404)
    d = {"id": r["id"], "url": r["url"], "title": r["title"] or "Untitled page",
         "score": r["score"] or 0, "total": r["total_tests"], "passed": r["passed_tests"],
         "failed": r["failed_tests"], "incomplete": r["incomplete_tests"],
         "scan_time": r["scan_time"],
         "violations": json.loads(r["violations_json"] or "[]"),
         "passes": json.loads(r["passes_json"] or "[]"),
         "incomplete_results": json.loads(r["incomplete_json"] or "[]")}
    d["analysis"] = analyze(d)
    return d

def user_scans(limit=100, with_json=False):
    cols = "id,url,title,score,failed_tests,scan_time" + (",violations_json" if with_json else "")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(f"SELECT {cols} FROM scans_new WHERE user_id = %s ORDER BY id DESC LIMIT %s",
                (session["user_id"], limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

@app.route("/health")
def health():
    return {"status": "ok", "service": "AccessGuard"}

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter username and password.", "error")
            return render_template("login.html")

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

        if user and check_password_hash(user["password_hash"], password):
            now = datetime.now()
            cur.execute(
                "UPDATE users SET last_login = %s WHERE id = %s",
                (now, user["id"])
            )
            cur.execute(
                """INSERT INTO login_history (user_id, username, login_time)
                   VALUES (%s, %s, %s)""",
                (user["id"], user["username"], now)
            )
            conn.commit()

            session["user_id"] = user["id"]
            session["username"] = user["username"]

            cur.close()
            conn.close()
            return redirect(url_for("index"))

        cur.close()
        conn.close()
        flash("Invalid username or password.", "error")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
        elif len(username) < 3:
            flash("Username must contain at least 3 characters.", "error")
        elif len(password) < 4:
            flash("Password must contain at least 4 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            conn = get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    """INSERT INTO users (username, password_hash, created_at)
                       VALUES (%s, %s, %s)""",
                    (username, generate_password_hash(password), datetime.now())
                )
                conn.commit()
                flash("Account created successfully. Please login.", "success")
                cur.close()
                conn.close()
                return redirect(url_for("login"))
            except mysql.connector.Error as e:
                conn.rollback()
                cur.close()
                conn.close()
                if getattr(e, "errno", None) == 1062:
                    flash("Username already exists.", "error")
                else:
                    flash("Could not create account. Check your database.", "error")

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    error = None
    if request.method == "POST":
        url = clean_url(request.form.get("url", ""))
        try:
            parsed = urlparse(url)
            if not parsed.netloc or parsed.scheme not in ("http", "https"):
                raise ValueError("Please enter a valid website URL.")
            check_target(url)
            data = scan_website(url)
            return redirect(url_for("scan_detail", sid=save_scan(data)))
        except Exception as e:
            error = str(e)
    return render_template("index.html", error=error, recent=user_scans(5))

@app.route("/scan/<int:sid>")
@login_required
def scan_detail(sid):
    return render_template("scan.html", d=load_scan(sid))

@app.route("/scan/<int:sid>/delete", methods=["POST"])
@login_required
def scan_delete(sid):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM scans_new WHERE id = %s AND user_id = %s", (sid, session["user_id"]))
    conn.commit()
    cur.close()
    conn.close()
    flash("Scan deleted.", "success")
    return redirect(url_for("history"))

@app.route("/scan/<int:sid>/export.<fmt>")
@login_required
def scan_export(sid, fmt):
    d = load_scan(sid)
    if fmt == "json":
        body, mime = json.dumps(d, indent=2, default=str), "application/json"
    elif fmt == "csv":
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["rule", "impact", "issue", "elements_affected", "selector", "how_to_fix"])
        for x in d["violations"]:
            for n in (x["nodes"] or [{}]):
                w.writerow([x["id"], x["impact"], x["help"], len(x["nodes"]),
                            " ".join(map(str, n.get("target", []))),
                            n.get("failureSummary", "").replace("\n", " | ")])
        body, mime = out.getvalue(), "text/csv"
    else:
        abort(404)
    return Response(body, mimetype=mime, headers={
        "Content-Disposition": f"attachment; filename=accessguard_scan_{sid}.{fmt}"})

@app.route("/dashboard")
@login_required
def dashboard():
    rows = user_scans(50, with_json=True)
    sev, rules = Counter(), {}
    for r in rows:
        for x in json.loads(r.pop("violations_json") or "[]"):
            sev[x["impact"]] += 1
            e = rules.setdefault(x["id"], {"help": x["help"], "impact": x["impact"], "count": 0})
            e["count"] += 1
    top = sorted(rules.items(), key=lambda kv: -kv[1]["count"])[:8]
    scores = [r["score"] or 0 for r in reversed(rows)]
    pts = ""
    if scores:
        step = 600 / max(len(scores) - 1, 1)
        pts = " ".join(f"{(i * step if len(scores) > 1 else 300):.1f},{150 - s * 1.4:.1f}"
                       for i, s in enumerate(scores))
    stats = {"count": len(rows), "avg": round(sum(scores) / len(scores)) if scores else 0,
             "best": max(rows, key=lambda r: r["score"] or 0) if rows else None,
             "worst": min(rows, key=lambda r: r["score"] or 0) if rows else None}
    return render_template("dashboard.html", stats=stats, sev=sev, top=top, pts=pts,
                           scores=scores, rows=rows[:6], sev_max=max(list(sev.values()) + [1]))

@app.route("/compare")
@login_required
def compare():
    scans = user_scans(100)
    a, b = request.args.get("a", type=int), request.args.get("b", type=int)
    res = None
    if a and b:
        A, B = load_scan(a), load_scan(b)
        fa = {v["id"]: v for v in A["violations"]}
        fb = {v["id"]: v for v in B["violations"]}
        res = {"A": A, "B": B, "delta": B["score"] - A["score"],
               "fixed": [fa[k] for k in fa if k not in fb],
               "new": [fb[k] for k in fb if k not in fa],
               "same": [fb[k] for k in fb if k in fa]}
    return render_template("compare.html", scans=scans, a=a, b=b, res=res)

@app.route("/history")
@login_required
def history():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT id,url,title,score,total_tests,passed_tests,failed_tests,
               incomplete_tests,scan_time,username
        FROM scans_new
        WHERE user_id = %s
        ORDER BY id DESC
    """, (session["user_id"],))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("history.html", rows=rows)

@app.route("/login-records")
@login_required
def login_records():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT id, username, login_time
        FROM login_history
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("login_records.html", rows=rows)

if __name__ == "__main__":
    init_db()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False
    )
