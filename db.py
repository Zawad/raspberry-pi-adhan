"""SQLite storage: settings, per-prayer config, hooks, event log."""
import json
import sqlite3
from datetime import datetime, timezone

from config import DB_PATH, DEFAULT_FAJR_MP3, DEFAULT_MP3, PRAYER_NAMES

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prayers (
    name    TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    volume  INTEGER NOT NULL DEFAULT 80,
    mp3     TEXT NOT NULL,
    device  TEXT
);
CREATE TABLE IF NOT EXISTS hooks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    position   TEXT NOT NULL CHECK (position IN ('before', 'after')),
    prayers    TEXT NOT NULL,
    days       TEXT NOT NULL,
    script     TEXT NOT NULL,
    enabled    INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT NOT NULL,
    type   TEXT NOT NULL,
    detail TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        for name in PRAYER_NAMES:
            mp3 = DEFAULT_FAJR_MP3 if name == "fajr" else DEFAULT_MP3
            conn.execute(
                "INSERT OR IGNORE INTO prayers (name, enabled, volume, mp3) VALUES (?, 1, 80, ?)",
                (name, mp3),
            )


def get_setting(key: str, default=None):
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_setting(key: str, value) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )


def get_prayers() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM prayers").fetchall()
    return [dict(r) for r in rows]


def get_prayer(name: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM prayers WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def update_prayer(name: str, fields: dict) -> None:
    allowed = {k: v for k, v in fields.items() if k in ("enabled", "volume", "mp3", "device")}
    if not allowed:
        return
    sets = ", ".join(f"{k} = ?" for k in allowed)
    with connect() as conn:
        conn.execute(f"UPDATE prayers SET {sets} WHERE name = ?", (*allowed.values(), name))


def get_hooks() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM hooks ORDER BY id").fetchall()
    hooks = []
    for r in rows:
        h = dict(r)
        h["prayers"] = json.loads(h["prayers"])
        h["days"] = json.loads(h["days"])
        hooks.append(h)
    return hooks


def add_hook(name: str, position: str, prayers: list[str], days: list[int], script: str, enabled: bool = True) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO hooks (name, position, prayers, days, script, enabled, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, position, json.dumps(prayers), json.dumps(days), script,
             int(enabled), datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def update_hook(hook_id: int, fields: dict) -> None:
    allowed = {}
    for k, v in fields.items():
        if k in ("name", "position", "script"):
            allowed[k] = v
        elif k in ("prayers", "days"):
            allowed[k] = json.dumps(v)
        elif k == "enabled":
            allowed[k] = int(v)
    if not allowed:
        return
    sets = ", ".join(f"{k} = ?" for k in allowed)
    with connect() as conn:
        conn.execute(f"UPDATE hooks SET {sets} WHERE id = ?", (*allowed.values(), hook_id))


def delete_hook(hook_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM hooks WHERE id = ?", (hook_id,))


def log_event(type_: str, detail: str) -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        conn.execute("INSERT INTO events (ts, type, detail) VALUES (?, ?, ?)", (ts, type_, detail))
    return {"ts": ts, "type": type_, "detail": detail}


def get_events(limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
