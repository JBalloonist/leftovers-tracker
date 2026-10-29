"""Leftovers tracker: a single-user Flask app backed by SQLite."""
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (Flask, g, jsonify, redirect, render_template, request,
                   send_file, session, url_for)

import labels

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Dev defaults apply only when run directly (`uv run app.py`) or under tests (LEFTOVERS_DEV=1).
DEV = __name__ == "__main__" or os.environ.get("LEFTOVERS_DEV") == "1"


def required_setting(name, dev_default):
    value = os.environ.get(name)
    if value:
        return value
    if DEV:
        return dev_default
    raise RuntimeError(f"{name} environment variable must be set (see README: Deploy to PythonAnywhere)")


app = Flask(__name__)
app.config.update(
    SECRET_KEY=required_setting("SECRET_KEY", "dev-only-change-me"),
    APP_PASSWORD=required_setting("APP_PASSWORD", "leftovers"),
    DB_PATH=os.environ.get("DB_PATH", os.path.join(BASE_DIR, "leftovers.db")),
    PERMANENT_SESSION_LIFETIME=timedelta(days=365),
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "0") == "1",
    SESSION_COOKIE_SAMESITE="Lax",
)

CODE_RE = re.compile(r"LO-\d{4,}")

SCHEMA = """
CREATE TABLE IF NOT EXISTS labels (
    code       TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    label_code TEXT NOT NULL REFERENCES labels(code),
    name       TEXT NOT NULL,
    stored_at  TEXT NOT NULL,
    removed_at TEXT,
    outcome    TEXT CHECK (outcome IN ('eaten', 'tossed'))
);
-- At most one item per label can be in the fridge at a time.
CREATE UNIQUE INDEX IF NOT EXISTS one_active_item_per_label
    ON items(label_code) WHERE removed_at IS NULL;
"""


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(app.config["DB_PATH"]) as db:
        db.executescript(SCHEMA)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("authed"):
            return view(*args, **kwargs)
        if request.path.startswith("/api/"):
            return jsonify(error="not logged in"), 401
        return redirect(url_for("login", next=request.full_path))
    return wrapped


def item_dict(row):
    return {k: row[k] for k in row.keys()} if row else None


# ---------- pages ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == app.config["APP_PASSWORD"]:
            session.permanent = True
            session["authed"] = True
            nxt = request.args.get("next", "/")
            return redirect(nxt if nxt.startswith("/") else "/")
        error = "Wrong password"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/l/<code>")
@login_required
def label_link(code):
    # QR codes encode this URL, so the iPhone's own Camera app opens straight to the label.
    return redirect(url_for("index", label=code.upper()))


# ---------- API ----------

@app.get("/api/items")
@login_required
def list_items():
    query = "SELECT * FROM items"
    if request.args.get("active", "1") == "1":
        query += " WHERE removed_at IS NULL"
    rows = get_db().execute(query + " ORDER BY stored_at").fetchall()
    return jsonify([item_dict(r) for r in rows])


@app.get("/api/labels/<code>")
@login_required
def get_label(code):
    code = code.upper()
    db = get_db()
    if not db.execute("SELECT 1 FROM labels WHERE code = ?", (code,)).fetchone():
        return jsonify(error=f"Unknown label {code}"), 404
    item = db.execute(
        "SELECT * FROM items WHERE label_code = ? AND removed_at IS NULL", (code,)
    ).fetchone()
    return jsonify(code=code, item=item_dict(item))


@app.post("/api/items")
@login_required
def add_item():
    data = request.get_json(silent=True) or {}
    code = (data.get("label_code") or "").strip().upper()
    name = (data.get("name") or "").strip()
    if not code or not name:
        return jsonify(error="label_code and name are required"), 400
    db = get_db()
    if not db.execute("SELECT 1 FROM labels WHERE code = ?", (code,)).fetchone():
        return jsonify(error=f"Unknown label {code}"), 404
    try:
        cur = db.execute(
            "INSERT INTO items (label_code, name, stored_at) VALUES (?, ?, ?)",
            (code, name, now_utc()),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error=f"Label {code} is already in use"), 409
    row = db.execute("SELECT * FROM items WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(item_dict(row)), 201


@app.post("/api/items/<int:item_id>/remove")
@login_required
def remove_item(item_id):
    outcome = (request.get_json(silent=True) or {}).get("outcome")
    if outcome not in ("eaten", "tossed"):
        return jsonify(error="outcome must be 'eaten' or 'tossed'"), 400
    db = get_db()
    cur = db.execute(
        "UPDATE items SET removed_at = ?, outcome = ? WHERE id = ? AND removed_at IS NULL",
        (now_utc(), outcome, item_id),
    )
    db.commit()
    if cur.rowcount == 0:
        return jsonify(error="Item not found or already removed"), 404
    return jsonify(item_dict(db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()))


@app.post("/labels/print")
@login_required
def print_labels():
    """Create new label codes (or reprint given ones) and return a printable PDF."""
    fmt = request.form.get("format", "sheet")
    reprint = CODE_RE.findall(request.form.get("reprint", "").upper())
    db = get_db()
    if reprint:
        codes = reprint
    else:
        count = max(1, min(int(request.form.get("count", 30)), 300))
        last = db.execute(
            "SELECT code FROM labels ORDER BY CAST(substr(code, 4) AS INTEGER) DESC LIMIT 1"
        ).fetchone()
        start = int(last["code"][3:]) + 1 if last else 1
        codes = [f"LO-{n:04d}" for n in range(start, start + count)]
        ts = now_utc()
        db.executemany("INSERT INTO labels (code, created_at) VALUES (?, ?)",
                       [(c, ts) for c in codes])
        db.commit()
    base_url = request.host_url.rstrip("/")
    pdf = labels.render_pdf(codes, base_url, fmt)
    return send_file(pdf, mimetype="application/pdf", as_attachment=True,
                     download_name=f"labels-{codes[0]}-{codes[-1]}.pdf")


init_db()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
