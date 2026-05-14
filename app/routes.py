"""
Flask routes — all HTTP endpoints for the calorie tracker.

Imports from helpers (pure logic), state (in-memory cache/selections),
and the database layer. No business logic lives here; routes are
thin glue between HTTP and the rest of the application.
"""

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from flask import Blueprint, g, flash, redirect, render_template, request, url_for

from api.nl_parser import is_natural_language, parse_food_input
from api.nutrition_api import search_food
from app.auth.auth import login_required
from app.config import DEFAULT_GOALS, MACRO_TYPES, MACRO_UNITS
from app.helpers import (
    compute_goal_stats,
    get_selected_dates,
    get_totals,
    update_food_cache,
)
from app import state
from storage.database import DBRecordManager, get_user_goals, set_user_goals

bp = Blueprint("main", __name__)
record_manager = DBRecordManager()


# ---------------------------------------------------------------------------
# Shared render helper
# ---------------------------------------------------------------------------

def render_main(start_date: str, end_date: str, log_time: str = None, **extra):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    user_search_results = []

    if g.user:
        username = g.user["username"]
        records = record_manager.query_user_records(username, start, end)
        goals = get_user_goals(username)
        user_search_results = state.search_results.get(username, [])
        selection = state.get_user_selection(username)
    else:
        records = OrderedDict()
        goals = dict(DEFAULT_GOALS)
        selection = {}

    log, totals = get_totals(records)
    if log_time is None:
        log_time = datetime.now().strftime("%Y-%m-%dT%H:%M")
    goal_stats = compute_goal_stats(totals, goals)

    ctx = dict(
        results=user_search_results,
        selection=selection,
        log=log,
        food_cache=state.food_cache,
        totals=totals,
        records=records,
        start_date=start_date,
        end_date=end_date,
        curr_time=log_time,
        macro_types=MACRO_TYPES,
        macro_units=MACRO_UNITS,
        goal_stats=goal_stats,
    )
    ctx.update(extra)
    return render_template("index.html", **ctx)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.route("/favicon.ico")
def favicon():
    return "", 204


@bp.route("/")
def index():
    start_date, end_date = get_selected_dates(request)
    return render_main(
        start_date,
        end_date,
        open_login=request.args.get("login") == "1",
        open_register=request.args.get("register") == "1",
    )


@bp.route("/handle_search", methods=["POST"])
@login_required
def handle_search():
    username = g.user["username"]
    query = request.form.get("query", "").strip()
    start_date, end_date = get_selected_dates(request)
    log_time = request.form.get("log_time")

    if is_natural_language(query):
        nl_items = parse_food_input(query)
        if nl_items:
            # Search FDC for all parsed items in parallel
            with ThreadPoolExecutor(max_workers=len(nl_items)) as executor:
                fdc_futures = {
                    executor.submit(search_food, item["food"]): item
                    for item in nl_items
                }

            auto_selection = {}
            logged_details = []
            all_results = []
            seen_ids: set = set()

            for future, item in fdc_futures.items():
                item_results = future.result()
                if not item_results:
                    continue
                top = item_results[0]
                fdc_id = int(top["fdc_id"])
                qty = item["quantity"]
                auto_selection[fdc_id] = auto_selection.get(fdc_id, 0) + qty
                logged_details.append({"name": top["name"], "quantity": qty, "fdc_id": fdc_id})
                for food in item_results:
                    if int(food["fdc_id"]) not in seen_ids:
                        seen_ids.add(int(food["fdc_id"]))
                        all_results.append(food)

            if auto_selection:
                update_food_cache(all_results)
                try:
                    ts = datetime.strptime(log_time, "%Y-%m-%dT%H:%M")
                except (ValueError, TypeError):
                    ts = datetime.now()

                record_manager.create_record(username, ts, auto_selection)

                records = record_manager.query_user_records(username, ts, ts + timedelta(minutes=1))
                nl_record_id = list(records.keys())[-1] if records else None

                state.search_results[username] = all_results
                return render_main(
                    start_date, end_date,
                    log_time=log_time,
                    nl_logged=logged_details,
                    nl_record_id=nl_record_id,
                    nl_query=query,
                    open_login=False,
                    open_register=False,
                )

    # Plain search fallback
    results = search_food(query)
    state.search_results[username] = results
    update_food_cache(results)
    return render_main(
        start_date, end_date,
        log_time=log_time,
        open_login=request.args.get("login") == "1",
        open_register=request.args.get("register") == "1",
    )


@bp.route("/update_selection", methods=["POST"])
@login_required
def update_selection():
    username = g.user["username"]
    selection = state.get_user_selection(username)

    food_id = int(request.form.get("fdc_id"))
    quantity = int(request.form.get("quantity"))

    if quantity == 0:
        selection.pop(food_id, None)
    else:
        selection[food_id] = quantity

    start_date, end_date = get_selected_dates(request)
    return render_main(start_date, end_date, log_time=request.form.get("log_time"))


@bp.route("/update_log", methods=["POST"])
@login_required
def update_log():
    username = g.user["username"]
    selection = state.get_user_selection(username)

    try:
        timestamp = datetime.strptime(request.form.get("log_time"), "%Y-%m-%dT%H:%M")
    except (ValueError, TypeError):
        timestamp = datetime.now()

    record_manager.create_record(username, timestamp, selection)
    selection.clear()

    start_date, end_date = get_selected_dates(request)
    return render_main(start_date, end_date)


@bp.route("/delete_log", methods=["POST"])
@login_required
def delete_log():
    username = g.user["username"]
    record_id = int(request.form.get("record_id"))
    record_manager.remove_record(record_id, username=username)
    start_date, end_date = get_selected_dates(request)
    return render_main(start_date, end_date, log_time=request.form.get("log_time"))


@bp.route("/set_goals", methods=["POST"])
@login_required
def set_goals():
    username = g.user["username"]
    goals = get_user_goals(username)

    for macro in MACRO_TYPES:
        try:
            val = int(float(request.form.get(f"goal_{macro}", goals[macro])))
            if val > 0:
                goals[macro] = val
        except (ValueError, TypeError):
            pass

    set_user_goals(username, goals)

    start_date, end_date = get_selected_dates(request)
    return render_main(start_date, end_date, log_time=request.form.get("log_time"))