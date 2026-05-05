import os
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / ".env")

from flask import Flask, flash, g, redirect, render_template, request, url_for
from api.nutrition_api import search_food
from storage.database import (
    init_db, DBRecordManager, save_food, load_food_cache,
    get_user_goals, set_user_goals
)
from ui.auth import bp as auth_bp

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-not-for-prod")
app.register_blueprint(auth_bp)
init_db()

macro_types = ["calories", "fat", "carbs", "protein"]
macro_units = {"calories": "",
         "fat": "g",
         "carbs": "g",
         "protein": "g"}

DEFAULT_GOALS = {"calories": 2000, "protein": 50, "carbs": 275, "fat": 78}

record_manager = DBRecordManager()
food_cache = load_food_cache()  # seeded from DB at startup, kept warm in memory

# global — holds the last search only, shared across all users
search_results = []

def get_totals(records):
    totals = {n: 0 for n in macro_types}
    log = {}

    for record in records.values():
        for (f_id, quantity) in record.info.items():
            info = food_cache.get(f_id)
            if not info:
                continue
            for t in macro_types:
                val = info.get(t, 0)
                if val is not None:
                    totals[t] += quantity * val
            log[f_id] = log.get(f_id, 0) + quantity

    return log, totals


def get_selected_dates(request):
    start_date = request.args.get("start_date") or request.form.get("start_date")
    end_date = request.args.get("end_date") or request.form.get("end_date")

    if start_date is None:
        now = datetime.now()
        day_start = datetime(now.year, now.month, now.day)
        start_date = day_start.date().isoformat()
        end_date = (day_start + timedelta(days=1)).date().isoformat()

    return start_date, end_date

def update_food_cache(search_results):
    # keep in memory dict and DB in sync
    for result in search_results:
        food_cache[int(result["fdc_id"])] = result
        save_food(result)

def compute_goal_stats(totals, goals):
    stats = {}
    for macro in macro_types:
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


def render_main(start_date, end_date, **extra):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    if g.user:
        records = record_manager.query_user_records(g.user["username"], start, end)
        goals = get_user_goals(g.user["username"])
    else:
        records = OrderedDict()
        goals = dict(DEFAULT_GOALS)

    log, totals = get_totals(records)
    curr_time = datetime.now().strftime("%Y-%m-%dT%H:%M")
    goal_stats = compute_goal_stats(totals, goals)

    ctx = dict(
        results=search_results,
        log=log,
        food_cache=food_cache,
        totals=totals,
        records=records,
        start_date=start_date,
        end_date=end_date,
        curr_time=curr_time,
        macro_types=macro_types,
        macro_units=macro_units,
        goal_stats=goal_stats,
    )
    ctx.update(extra)
    return render_template("index.html", **ctx)


@app.route("/")
def index():
    start_date, end_date = get_selected_dates(request)
    return render_main(
        start_date,
        end_date,
        open_login=request.args.get("login") == "1",
        open_register=request.args.get("register") == "1",
    )

@app.route('/handle_form', methods=['POST'])
def handle_form():
    global search_results
    user_input = request.form.get('query')
    search_results = search_food(user_input)
    update_food_cache(search_results)
    start_date, end_date = get_selected_dates(request)

    return render_main(
        start_date,
        end_date,
        open_login=request.args.get("login") == "1",
        open_register=request.args.get("register") == "1",
    )
    
@app.route('/update_log', methods=['POST'])
def update_log():
    start_date, end_date = get_selected_dates(request)
    if g.user is None:
        flash("Please sign in to add food to your log.")
        return redirect(url_for("index", start_date=start_date, end_date=end_date))

    food_id = int(request.form.get('fdc_id'))
    quantity = int(request.form.get('quantity'))
    t = request.form.get('time')
    try:
        time_stamp = datetime.strptime(t, "%Y-%m-%dT%H:%M")
    except (ValueError, TypeError):
        time_stamp = datetime.now()
    record_manager.create_record(g.user["username"], time_stamp, {food_id: quantity})

    return render_main(start_date, end_date)

@app.route('/delete_log', methods=['POST'])
def delete_log():
    start_date, end_date = get_selected_dates(request)
    if g.user is None:
        flash("Please sign in to delete log entries.")
        return redirect(url_for("index", start_date=start_date, end_date=end_date))

    record_id = int(request.form.get('record_id'))
    record_manager.remove_record(record_id, g.user["username"])

    return render_main(start_date, end_date)

@app.route('/set_goals', methods=['POST'])
def set_goals():
    start_date, end_date = get_selected_dates(request)
    if g.user is None:
        flash("Please sign in to update goals.")
        return redirect(url_for("index", start_date=start_date, end_date=end_date))

    username = g.user["username"]
    goals = get_user_goals(username)
    for macro in macro_types:
        try:
            val = int(request.form.get(f'goal_{macro}', goals[macro]))
            if val > 0:
                goals[macro] = val
        except (ValueError, TypeError):
            pass
    set_user_goals(username, goals)
 
    return render_main(start_date, end_date)
