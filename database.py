import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd


DB_PATH = Path("assistant.db")


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT NOT NULL UNIQUE,
                company TEXT,
                email TEXT,
                notes TEXT,
                status TEXT DEFAULT 'new',
                dnc INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                phone TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                status TEXT DEFAULT 'started',
                transcript TEXT,
                ai_summary TEXT,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )


def upsert_leads(df):
    count = 0
    timestamp = now_iso()
    with connect() as conn:
        for row in df.to_dict(orient="records"):
            phone = str(row.get("phone", "")).strip()
            if not phone:
                continue
            conn.execute(
                """
                INSERT INTO leads (name, phone, company, email, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(phone) DO UPDATE SET
                    name=excluded.name,
                    company=excluded.company,
                    email=excluded.email,
                    notes=excluded.notes,
                    updated_at=excluded.updated_at
                """,
                (
                    str(row.get("name", "")).strip(),
                    phone,
                    str(row.get("company", "")).strip(),
                    str(row.get("email", "")).strip(),
                    str(row.get("notes", "")).strip(),
                    timestamp,
                    timestamp,
                ),
            )
            count += 1
    return count


def _rows_to_df(rows):
    return pd.DataFrame([dict(row) for row in rows])


def get_leads(include_dnc=False):
    sql = "SELECT * FROM leads"
    if not include_dnc:
        sql += " WHERE dnc = 0"
    sql += " ORDER BY id DESC"
    with connect() as conn:
        return _rows_to_df(conn.execute(sql).fetchall())


def get_lead(lead_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return dict(row) if row else None


def update_lead_status(lead_id, status):
    with connect() as conn:
        conn.execute(
            "UPDATE leads SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), lead_id),
        )


def mark_dnc(lead_id):
    with connect() as conn:
        conn.execute(
            "UPDATE leads SET dnc = 1, status = 'dnc', updated_at = ? WHERE id = ?",
            (now_iso(), lead_id),
        )


def start_call(lead_id, phone):
    timestamp = now_iso()
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO calls (lead_id, phone, started_at, status) VALUES (?, ?, ?, 'started')",
            (lead_id, phone, timestamp),
        )
        conn.execute(
            "UPDATE leads SET status = 'calling', updated_at = ? WHERE id = ?",
            (timestamp, lead_id),
        )
        return cursor.lastrowid


def update_call(call_id, status, transcript, ai_summary):
    with connect() as conn:
        conn.execute(
            "UPDATE calls SET status = ?, transcript = ?, ai_summary = ? WHERE id = ?",
            (status, transcript, ai_summary, call_id),
        )


def end_call(call_id, status, transcript, ai_summary):
    with connect() as conn:
        conn.execute(
            """
            UPDATE calls
            SET ended_at = ?, status = ?, transcript = ?, ai_summary = ?
            WHERE id = ?
            """,
            (now_iso(), status or "ended", transcript, ai_summary, call_id),
        )


def get_calls():
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT calls.*, leads.name, leads.company
            FROM calls
            LEFT JOIN leads ON leads.id = calls.lead_id
            ORDER BY calls.id DESC
            """
        ).fetchall()
    return _rows_to_df(rows)


def get_call(call_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
    return dict(row) if row else None


def get_setting(key, default=""):
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value),
        )


def count_calls_on_date(day_iso):
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total FROM calls WHERE substr(started_at, 1, 10) = ?",
            (day_iso,),
        ).fetchone()
    return int(row["total"])


def seconds_until_delay_passed(last_started_at, delay_seconds):
    try:
        last = datetime.fromisoformat(last_started_at)
        elapsed = (datetime.now().astimezone() - last).total_seconds()
        return max(0, int(delay_seconds - elapsed))
    except Exception:
        return 0
