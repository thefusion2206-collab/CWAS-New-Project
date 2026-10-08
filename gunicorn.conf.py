import os

bind = "0.0.0.0:" + os.environ.get("PORT", "5000")
workers = 1
timeout = 180

def on_starting(server):
    from app import init_db
    init_db()
