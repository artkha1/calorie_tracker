import os
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Resolve project root so .env loads even when cwd differs (e.g. IDE runners).
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / ".env")

from supabase import Client, create_client

DEFAULT_GOALS = {"calories": 2000, "protein": 50, "carbs": 275, "fat": 78}

# PostgreSQL reserved word — PostgREST requires a quoted identifier.
_LOG_TS_COL = '"timestamp"'
_LOG_SELECT = 'id,fdc_id,quantity,"timestamp"'

_client: Optional[Client] = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = (os.getenv("SUPABASE_URL") or "").strip()
        key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not url or not key:
            raise RuntimeError(
                "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in your environment or .env file."
            )
        _client = create_client(url, key)
    return _client


def init_db() -> None:
    """Ensure Supabase credentials are present. Create tables in Supabase SQL Editor."""
    get_supabase()


def save_food(food: dict) -> None:
    sb = get_supabase()
    payload = {
        "fdc_id": int(food.get("fdc_id")),
        "name": food.get("name"),
        "calories": food.get("calories"),
        "protein": food.get("protein"),
        "fat": food.get("fat"),
        "carbs": food.get("carbs"),
    }
    sb.table("food_cache").upsert(payload, on_conflict="fdc_id").execute()


def load_food_cache() -> dict:
    sb = get_supabase()
    res = sb.table("food_cache").select(
        "fdc_id,name,calories,protein,fat,carbs"
    ).execute()
    rows = res.data or []
    return {int(r["fdc_id"]): dict(r) for r in rows}


def get_user_goals(username: str) -> dict:
    sb = get_supabase()
    res = (
        sb.table("goals")
        .select("macro,value")
        .eq("username", username)
        .execute()
    )
    rows = res.data or []
    goals = dict(DEFAULT_GOALS)
    for r in rows:
        goals[r["macro"]] = r["value"]
    return goals


def set_user_goals(username: str, goals: dict) -> None:
    sb = get_supabase()
    payload = [
        {"username": username, "macro": macro, "value": value}
        for macro, value in goals.items()
    ]
    sb.table("goals").upsert(payload, on_conflict="username,macro").execute()


class Record:
    def __init__(self, timestamp, info, user_id, record_id):
        self.id = record_id
        self.timestamp = timestamp
        self.info = info
        self.user_id = user_id


class DBRecordManager:
    def create_record(self, user_id, timestamp, info):
        sb = get_supabase()
        for fdc_id, quantity in info.items():
            sb.table("log_entries").insert(
                {
                    "username": user_id,
                    "fdc_id": int(fdc_id),
                    "quantity": quantity,
                    "timestamp": timestamp.isoformat(),  # column name in DB is "timestamp"
                }
            ).execute()

    def query_user_records(self, user_id, start_time=None, end_time=None):
        sb = get_supabase()
        q = (
            sb.table("log_entries")
            .select(_LOG_SELECT)
            .eq("username", user_id)
            .order("id")
        )

        if start_time:
            q = q.gte(_LOG_TS_COL, start_time.isoformat())
        if end_time:
            q = q.lt(_LOG_TS_COL, end_time.isoformat())

        res = q.execute()
        rows = res.data or []

        results = OrderedDict()
        for row in rows:
            ts_raw = row["timestamp"]
            if isinstance(ts_raw, str) and ts_raw.endswith("Z"):
                ts_raw = ts_raw[:-1] + "+00:00"
            results[row["id"]] = Record(
                timestamp=datetime.fromisoformat(ts_raw),
                info={row["fdc_id"]: row["quantity"]},
                user_id=user_id,
                record_id=row["id"],
            )
        return results

    def remove_record(self, record_id, username: Optional[str] = None):
        sb = get_supabase()
        delete_q = sb.table("log_entries").delete().eq("id", record_id)
        if username is not None:
            delete_q = delete_q.eq("username", username)
        delete_q.execute()
