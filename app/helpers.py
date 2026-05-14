"""
Pure helper functions — no Flask context, no DB calls, easily unit-tested.
"""

from collections import OrderedDict
from datetime import datetime, timedelta

from app.config import DEFAULT_GOALS, MACRO_TYPES
from app import state


def get_selected_dates(req) -> tuple[str, str]:
    """Return (start_date, end_date) ISO strings from the request, defaulting to today."""
    start_date = req.args.get("start_date") or req.form.get("start_date")
    end_date = req.args.get("end_date") or req.form.get("end_date")

    if start_date is None:
        now = datetime.now()
        day_start = datetime(now.year, now.month, now.day)
        start_date = day_start.date().isoformat()
        end_date = (day_start + timedelta(days=1)).date().isoformat()

    return start_date, end_date


def get_totals(records: OrderedDict) -> tuple[dict, dict]:
    """
    Compute per-food quantity log and macro totals from a set of records.
    Foods not present in food_cache are skipped silently.
    """
    totals = {n: 0 for n in MACRO_TYPES}
    log: dict = {}

    for record in records.values():
        for fdc_id, quantity in record.info.items():
            info = state.food_cache.get(fdc_id)
            if not info:
                continue
            for macro in MACRO_TYPES:
                val = info.get(macro, 0)
                if val is not None:
                    totals[macro] += quantity * val
            log[fdc_id] = log.get(fdc_id, 0) + quantity

    return log, totals


def compute_goal_stats(totals: dict, goals: dict) -> dict:
    """Return per-macro stats dict for rendering progress bars and summaries."""
    stats = {}
    for macro in MACRO_TYPES:
        consumed = round(totals.get(macro, 0), 1)
        goal = goals.get(macro, DEFAULT_GOALS[macro])
        remaining = round(max(goal - consumed, 0), 1)
        over = round(consumed - goal, 1) if consumed > goal else 0
        progress = min(round((consumed / goal) * 100, 1), 100) if goal > 0 else 0
        stats[macro] = {
            "consumed": consumed,
            "goal": goal,
            "remaining": remaining,
            "over": over,
            "progress": progress,
        }
    return stats


def update_food_cache(results: list) -> None:
    """Add FDC search results to the in-memory cache and persist to DB."""
    from storage.database import save_food
    for food in results:
        state.food_cache[int(food["fdc_id"])] = food
        save_food(food)