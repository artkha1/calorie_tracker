import sqlite3
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "calorie_tracker.db"

DEFAULT_GOALS = {"calories": 2000, "protein": 50, "carbs": 275, "fat": 78}


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
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
            CREATE TABLE IF NOT EXISTS food_cache (
                fdc_id INTEGER PRIMARY KEY,
                name TEXT,
                calories REAL,
                protein REAL,
                fat REAL,
                carbs REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                fdc_id INTEGER NOT NULL,
                quantity REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS goals (
                username TEXT NOT NULL,
                macro TEXT NOT NULL,
                value REAL NOT NULL,
                PRIMARY KEY (username, macro)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                timestamp TEXT
            )
            """
        )
        conn.commit()

def save_food(food: dict) -> None:
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO food_cache (fdc_id, name, calories, protein, fat, carbs)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(food.get("fdc_id")),
                food.get("name"),
                food.get("calories"),
                food.get("protein"),
                food.get("fat"),
                food.get("carbs"),
            ),
        )
        conn.commit()


def load_food_cache() -> dict:
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT fdc_id, name, calories, protein, fat, carbs FROM food_cache"
        ).fetchall()
    return {row["fdc_id"]: dict(row) for row in rows}

def get_user_goals(username: str) -> dict:
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT macro, value FROM goals WHERE username = ?", (username,)
        ).fetchall()
    if not rows:
        return dict(DEFAULT_GOALS)
    # start from defaults so any macro not yet saved still has a value
    goals = dict(DEFAULT_GOALS)
    for row in rows:
        goals[row["macro"]] = row["value"]
    return goals


def set_user_goals(username: str, goals: dict) -> None:
    with _get_connection() as conn:
        for macro, value in goals.items():
            conn.execute(
                """
                INSERT OR REPLACE INTO goals (username, macro, value)
                VALUES (?, ?, ?)
                """,
                (username, macro, value),
            )
        conn.commit()


class Record:
    def __init__(self, timestamp, info, user_id, record_id):
        self.id = record_id
        self.timestamp = timestamp
        self.info = info
        self.user_id = user_id


class DBRecordManager:

    def create_record(self, user_id, timestamp, info):
        with _get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO records (username, timestamp)
                VALUES (?, ?)
                """,
                (user_id, timestamp.isoformat()),
            )

            record_id = cursor.lastrowid

            for fdc_id, quantity in info.items():
                conn.execute(
                    """
                    INSERT INTO log_entries (record_id, fdc_id, quantity)
                    VALUES (?, ?, ?)
                    """,
                    (record_id, int(fdc_id), quantity),
                )
            conn.commit()

    def query_user_records(self, user_id, start_time=None, end_time=None):
        # strings sort in order, so string comparison works for date filtering
        sql = """
        SELECT 
            l.record_id,
            l.fdc_id,
            l.quantity,
            r.timestamp
        FROM log_entries l
        JOIN records r ON l.record_id = r.id
        WHERE r.username = ?
        """

        # sql = "SELECT id, fdc_id, quantity, timestamp FROM log_entries WHERE username = ?"
        params = [user_id]
        if start_time:
            params.append(start_time.isoformat())
            sql += " AND r.timestamp >= ?"
        if end_time:
            params.append(end_time.isoformat())
            sql += " AND r.timestamp < ?"
        
        sql += "ORDER BY l.record_id, l.id"

        with _get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        
        # Group queries together by record id
        queries_by_record_id = OrderedDict()
        record_timestamps = OrderedDict()
        for row in rows:
            record_id = row["record_id"]
            fdc_id = row["fdc_id"]
            qty = row["quantity"]
            
            if record_id not in queries_by_record_id:
                queries_by_record_id[record_id] = []

                timestamp=datetime.fromisoformat(row["timestamp"])
                record_timestamps[record_id] = timestamp

            queries_by_record_id[record_id].append((fdc_id, qty))
        
        results = OrderedDict()
        for r_id, queries in queries_by_record_id.items():
            results[r_id] = Record(
                timestamp=record_timestamps[r_id],
                info={q[0]: q[1] for q in queries},
                user_id=user_id,
                record_id=r_id,
            )
        return results

    def remove_record(self, record_id):
        with _get_connection() as conn:
            conn.execute("DELETE FROM log_entries WHERE record_id = ?", (record_id,))
            conn.commit()
