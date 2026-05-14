import os
import sqlite3
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Resolve project root so .env loads even when cwd differs (e.g. IDE runners).
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / ".env")

# Database file lives at storage/calorie_tracker.db by default,
# but can be overridden via the DATABASE_PATH env var (useful for tests).
_DEFAULT_DB_PATH = Path(__file__).resolve().parent / "calorie_tracker.db"
DB_PATH = Path(os.getenv("DATABASE_PATH", str(_DEFAULT_DB_PATH)))

DEFAULT_GOALS = {"calories": 2000, "protein": 50, "carbs": 275, "fat": 78}


@contextmanager
def _get_conn():
    """Yield a SQLite connection with row_factory and foreign-key support."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create all tables if they don't already exist."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                username  TEXT PRIMARY KEY,
                password  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS food_cache (
                fdc_id    INTEGER PRIMARY KEY,
                name      TEXT,
                calories  REAL,
                protein   REAL,
                fat       REAL,
                carbs     REAL
            );

            CREATE TABLE IF NOT EXISTS goals (
                username  TEXT NOT NULL,
                macro     TEXT NOT NULL,
                value     REAL NOT NULL,
                PRIMARY KEY (username, macro),
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS records (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                username  TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS log_entries (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                fdc_id    INTEGER NOT NULL,
                quantity  REAL NOT NULL,
                FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
            );
        """)


# ---------------------------------------------------------------------------
# Food cache
# ---------------------------------------------------------------------------

def save_food(food: dict) -> None:
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO food_cache (fdc_id, name, calories, protein, fat, carbs)
            VALUES (:fdc_id, :name, :calories, :protein, :fat, :carbs)
            ON CONFLICT(fdc_id) DO UPDATE SET
                name     = excluded.name,
                calories = excluded.calories,
                protein  = excluded.protein,
                fat      = excluded.fat,
                carbs    = excluded.carbs
        """, {
            "fdc_id":   int(food.get("fdc_id")),
            "name":     food.get("name"),
            "calories": food.get("calories"),
            "protein":  food.get("protein"),
            "fat":      food.get("fat"),
            "carbs":    food.get("carbs"),
        })


def load_food_cache() -> dict:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT fdc_id, name, calories, protein, fat, carbs FROM food_cache"
        ).fetchall()
    return {int(r["fdc_id"]): dict(r) for r in rows}


# ---------------------------------------------------------------------------
# User goals
# ---------------------------------------------------------------------------

def get_user_goals(username: str) -> dict:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT macro, value FROM goals WHERE username = ?", (username,)
        ).fetchall()
    goals = dict(DEFAULT_GOALS)
    for r in rows:
        goals[r["macro"]] = r["value"]
    return goals


def set_user_goals(username: str, goals: dict) -> None:
    with _get_conn() as conn:
        for macro, value in goals.items():
            conn.execute("""
                INSERT INTO goals (username, macro, value) VALUES (?, ?, ?)
                ON CONFLICT(username, macro) DO UPDATE SET value = excluded.value
            """, (username, macro, value))


# ---------------------------------------------------------------------------
# Users  (used by auth.py — mirrors the old Supabase users table)
# ---------------------------------------------------------------------------

def get_user(username: str) -> Optional[dict]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT username, password FROM users WHERE username = ?", (username,)
        ).fetchone()
    return dict(row) if row else None


def create_user(username: str, password_hash: str) -> None:
    """Raises sqlite3.IntegrityError if username already exists."""
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password_hash),
        )


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

class Record:
    def __init__(self, timestamp, info, user_id, record_id):
        self.id = record_id
        self.timestamp = timestamp
        self.info = info
        self.user_id = user_id


class DBRecordManager:
    def create_record(self, user_id, timestamp, info):
        with _get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO records (username, timestamp) VALUES (?, ?)",
                (user_id, timestamp.isoformat()),
            )
            record_id = cur.lastrowid

            if info:
                conn.executemany(
                    "INSERT INTO log_entries (record_id, fdc_id, quantity) VALUES (?, ?, ?)",
                    [(record_id, int(fdc_id), quantity) for fdc_id, quantity in info.items()],
                )

    def query_user_records(self, user_id, start_time=None, end_time=None):
        query = """
            SELECT le.record_id, le.fdc_id, le.quantity, r.timestamp
            FROM log_entries le
            JOIN records r ON le.record_id = r.id
            WHERE r.username = ?
        """
        params: list = [user_id]

        if start_time:
            query += " AND r.timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time:
            query += " AND r.timestamp < ?"
            params.append(end_time.isoformat())

        query += " ORDER BY le.record_id"

        with _get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        queries_by_record_id: OrderedDict = OrderedDict()
        record_timestamps: dict = {}

        for row in rows:
            r_id = row["record_id"]
            ts_raw = row["timestamp"]

            if r_id not in queries_by_record_id:
                queries_by_record_id[r_id] = []
                # Handle both 'Z' suffix (legacy) and plain ISO strings
                if isinstance(ts_raw, str) and ts_raw.endswith("Z"):
                    ts_raw = ts_raw[:-1] + "+00:00"
                record_timestamps[r_id] = datetime.fromisoformat(ts_raw)

            queries_by_record_id[r_id].append((row["fdc_id"], row["quantity"]))

        results: OrderedDict = OrderedDict()
        for r_id, queries in queries_by_record_id.items():
            results[r_id] = Record(
                timestamp=record_timestamps[r_id],
                info={q[0]: q[1] for q in queries},
                user_id=user_id,
                record_id=r_id,
            )

        return results

    def remove_record(self, record_id, username: str = None):
        with _get_conn() as conn:
            if username is not None:
                # Verify ownership before deleting
                row = conn.execute(
                    "SELECT id FROM records WHERE id = ? AND username = ?",
                    (record_id, username),
                ).fetchone()
                if not row:
                    return  # record doesn't exist or belongs to another user
            # log_entries deleted automatically via ON DELETE CASCADE
            conn.execute("DELETE FROM records WHERE id = ?", (record_id,))