import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "calorie_tracker.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create required tables if they do not already exist."""
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                calories REAL,
                protein REAL,
                fat REAL,
                carbs REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def add_food(food: dict) -> int:
    """
    Insert one food record and return the inserted row id.
    Expected keys: name, calories, protein, fat, carbs.
    """
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO foods (name, calories, protein, fat, carbs)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                food.get("name"),
                food.get("calories"),
                food.get("protein"),
                food.get("fat"),
                food.get("carbs"),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_foods(limit: int = 50) -> list[dict]:
    """Return the most recently added foods, newest first."""
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, calories, protein, fat, carbs, created_at
            FROM foods
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]