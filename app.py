import json
import os
import sqlite3
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "notes.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_db_schema():
    with get_db_connection() as conn:
        cols = conn.execute("PRAGMA table_info(notes)").fetchall()
        existing = {column[1] for column in cols}

        if "title" not in existing:
            conn.execute("ALTER TABLE notes ADD COLUMN title TEXT NOT NULL DEFAULT ''")

        conn.commit()


def init_db():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                text TEXT NOT NULL DEFAULT 'New note',
                x INTEGER NOT NULL DEFAULT 100,
                y INTEGER NOT NULL DEFAULT 100,
                width INTEGER NOT NULL DEFAULT 180,
                height INTEGER NOT NULL DEFAULT 140,
                checked INTEGER NOT NULL DEFAULT 0,
                rotation REAL NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()

    ensure_db_schema()


init_db()


@app.route("/")
def home():
    with get_db_connection() as conn:
        notes = conn.execute(
            "SELECT id, title, text, x, y, width, height, checked, rotation FROM notes ORDER BY id ASC"
        ).fetchall()

    return render_template("index.html", notes=[dict(note) for note in notes])


@app.route("/notes", methods=["POST"])
def create_note():
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", ""))
    text = str(payload.get("text", "New note"))
    x = int(payload.get("x", 100))
    y = int(payload.get("y", 100))
    width = int(payload.get("width", 540))
    height = int(payload.get("height", 420))
    checked = int(bool(payload.get("checked", False)))
    rotation = float(payload.get("rotation", 0))

    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO notes (title, text, x, y, width, height, checked, rotation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, text, x, y, width, height, checked, rotation),
        )
        conn.commit()
        note_id = cursor.lastrowid

    return jsonify({
        "id": note_id,
        "title": title,
        "text": text,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "checked": checked,
        "rotation": rotation,
    })


@app.route("/notes/<int:note_id>", methods=["PUT"])
def update_note(note_id):
    payload = request.get_json(silent=True) or {}
    if not payload:
        return jsonify({"error": "No payload provided"}), 400

    allowed_fields = {"title", "text", "x", "y", "width", "height", "checked", "rotation"}
    updates = []
    values = []

    for key in allowed_fields:
        if key in payload:
            if key in {"text", "title"}:
                value = str(payload[key])
            elif key in {"checked"}:
                value = int(bool(payload[key]))
            elif key in {"x", "y", "width", "height"}:
                value = int(payload[key])
            else:
                value = float(payload[key])
            updates.append(f"{key} = ?")
            values.append(value)

    if not updates:
        return jsonify({"error": "No valid update fields"}), 400

    values.append(note_id)
    with get_db_connection() as conn:
        conn.execute(
            f"UPDATE notes SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        conn.commit()

    return jsonify({"status": "updated", "id": note_id})


@app.route("/notes/<int:note_id>", methods=["DELETE"])
def delete_note(note_id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
    return jsonify({"status": "deleted", "id": note_id})


@app.route("/notes/clear", methods=["POST"])
def clear_notes():
    with get_db_connection() as conn:
        conn.execute("DELETE FROM notes")
        conn.commit()
    return jsonify({"status": "cleared"})


def open_browser():
    port = int(os.environ.get("PORT", "5000"))
    webbrowser.open_new(f"http://127.0.0.1:{port}/")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7000"))
    threading.Timer(1.0, open_browser).start()
    app.run(host="0.0.0.0", port=port, debug=False)
