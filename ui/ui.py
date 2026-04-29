import os
from flask import Flask, request, render_template, g
from api.nutrition_api import search_food
from collections import OrderedDict
from datetime import datetime, timedelta
from dotenv import load_dotenv
from storage.database import init_db
from ui.auth import bp as auth_bp, login_required

load_dotenv()
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

class Record:
    """
        Record objects store 'update log' transactions.

        timestamp (datetime): Timestamp of when transaction was made
        info (dict): A dict with keys as food ids and values as quantities 
        user_id: A unique identifier for the user who initiated the transaction
        record_id: A unique identifier for the record
    """

    def __init__(self, timestamp, info, user_id, record_id):
        self.id = record_id
        self.timestamp = timestamp
        self.info = info
        self.user_id = user_id

class RecordManager:
    def __init__(self):
        self._n_records = 0
        # Records is a dict with keys as ids and values as records. 
        self._records = dict()
        self._users_to_records = dict()

    def create_record(self, user_id, timestamp, info):
        # Use the total number of records created as id
        record_id = self._n_records         
        
        # Create a record oobject
        record = Record(timestamp, info, user_id, record_id)

        # Log the record
        self._records[record_id] = record

        # If this is the first record for the user, 
        # initalize a dict to hold record ids for the user
        if user_id not in self._users_to_records:
            self._users_to_records[user_id] = OrderedDict()
        
        # Log record for user 
        self._users_to_records[user_id][record_id] = record
        
        # Increment record count
        self._n_records += 1
    
    """
        Get all records beloning to a user.

        Returns:
            If a user has no records: 
            None
            
            Otherwise:
            An ordered dict with keys as record ids and values as records
    """
    def query_user_records(self, user_id, start_time=None, end_time=None):
        if user_id not in self._users_to_records:
            return {}
        
        user_records = self._users_to_records[user_id]
        if not start_time and not end_time:
            return user_records

        # TODO: Speed Up?
        # This is a slow way to gather results
        # But, since this will be replaced by persistent memory, 
        # it may be sufficent for now
        results = OrderedDict()
        for record_id, record in user_records.items():
            r_time = record.timestamp
            include = True

            if start_time:
                include = (r_time - start_time).total_seconds() >= 0
            if end_time:
                include = include and (end_time - r_time).total_seconds() > 0

            if include:
                results[record_id] = record

        return results

    def remove_record(self, record_id):
        if record_id not in self._records:
            return

        record = self._records[record_id]
        
        user_id = record.user_id
        del self._users_to_records[user_id][record_id]

        del self._records[record_id]

record_manager = RecordManager()

# TODO: Replace with session cookie (or persistent storage w/ login system)
userID = "John"

# TODO: Properly implement a food cache
food_cache = {} # Only need to store foods in log

# TODO: Storing previous search results in a global variable has many issues
# Proper asynchronous updates should be implemented using Ajax
search_results = [] # store search results to avoid repeated queries

# Per-user macro goals (will move to DB with auth)
macro_goals = {userID: dict(DEFAULT_GOALS)}

# Get totals for user since timestamp
def get_totals(records):

    # Initalize dict to hold nutrition totals
    totals = {n: 0 for n in macro_types}

    log = {}

    for record in records.values():
        for (f_id, quantity) in record.info.items():
            # Get nutrition data for food id f_id
            info = food_cache.get(f_id)

            # Skip record if there is no data for food id
            if not info:
                continue

            # Update nutrition totals 
            for t in macro_types:
                val = info.get(t, 0)
                if val is not None:
                    totals[t] += quantity * val

            log[f_id] = log.get(f_id, 0) + quantity

    return log, totals

# Extract the selected date from request;
# if a date is not selected, return the 
# current day

def get_selected_dates(request):
    start_date = request.args.get("start_date") or request.form.get("start_date")
    end_date = request.args.get("end_date") or request.form.get("end_date")

    if start_date is None:
        # Set start date to start of current day
        now = datetime.now()
        day_start = datetime(now.year, now.month, now.day) 
        start_date = day_start.date().isoformat()

        # Set end date to next day
        end_date = (day_start + timedelta(days=1)).date().isoformat()


    return start_date, end_date 

def update_food_cache(search_results):
    for result in search_results:
        food_cache[int(result["fdc_id"])] = result

def compute_goal_stats(totals, goals):
    """For each macro, compute consumed, goal, remaining, and progress %."""
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


def render_main(start_date, end_date):
    """Single helper so every route passes the same context."""
    
    # Parse selected date (assume start of day)
    start = datetime.strptime(start_date, "%Y-%m-%d")
    
    # Get nutritional information for the day
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # Get all records for user between start time stamp and end time stamp
    records = record_manager.query_user_records(g.user["username"], start, end)

    # Get totals for records
    log, totals = get_totals(records)

    # FIX (Artem): datetime-local inputs require format without seconds
    curr_time = datetime.now().strftime("%Y-%m-%dT%H:%M")

    goals = macro_goals.get(userID, dict(DEFAULT_GOALS))
    goal_stats = compute_goal_stats(totals, goals)

    return render_template(
        'index.html',
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


@app.route("/")
@login_required
def index():
    start_date, end_date = get_selected_dates(request)
    return render_main(start_date, end_date)

@app.route('/handle_form', methods=['POST'])
@login_required
def handle_form():
    global search_results
    user_input = request.form.get('query')
    search_results = search_food(user_input)
    update_food_cache(search_results)
    start_date, end_date = get_selected_dates(request)

    return render_main(start_date, end_date)
    
# TODO: Support multiple types of foods in record
@app.route('/update_log', methods=['POST'])
@login_required
def update_log():
    food_id = int(request.form.get('fdc_id'))
    quantity = int(request.form.get('quantity'))

    # Create timestamp from logged time
    t = request.form.get('time')
    try:
        # FIX: parse format matching the corrected datetime-local output (no seconds)
        time_stamp = datetime.strptime(t, "%Y-%m-%dT%H:%M")
    except (ValueError, TypeError):
        time_stamp = datetime.now()

    # Create record of update
    record_manager.create_record(g.user["username"], time_stamp, {food_id: quantity})

    start_date, end_date = get_selected_dates(request)
    return render_main(start_date, end_date)

@app.route('/delete_log', methods=['POST'])
@login_required
def delete_log():
    # Remove record
    record_id = int(request.form.get('record_id'))
    record_manager.remove_record(record_id)

    start_date, end_date = get_selected_dates(request)
    return render_main(start_date, end_date)

@app.route('/set_goals', methods=['POST'])
def set_goals():
    """Update the user's daily macro goals."""
    goals = macro_goals.get(userID, dict(DEFAULT_GOALS))
    for macro in macro_types:
        try:
            val = int(request.form.get(f'goal_{macro}', goals[macro]))
            if val > 0:
                goals[macro] = val
        except (ValueError, TypeError):
            pass
    macro_goals[userID] = goals
 
    start_date, end_date = get_selected_dates(request)
    return render_main(start_date, end_date)
