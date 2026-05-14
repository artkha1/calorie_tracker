"""
In-memory server state shared across requests.

food_cache   — fdc_id → food dict, seeded from DB on startup and kept warm.
search_results — username → list of food dicts from the last search.
selections   — username → {fdc_id: quantity} pending log entry.

Note: this is process-local state. It resets on every deploy/restart.
"""

food_cache: dict = {}       # populated in create_app() after init_db()
search_results: dict = {}   # username -> [food, ...]
selections: dict = {}       # username -> {fdc_id: quantity}


def get_user_selection(username: str) -> dict:
    if username not in selections:
        selections[username] = {}
    return selections[username]