from flask import Flask, request, render_template
from api.nutrition_api import search_food
from collections import OrderedDict
from datetime import datetime, timedelta

app = Flask(__name__)

class Record:
    """
        Record objects store 'update log' transactions.

        timestamp (datetime): Timestamp of when transaction was made
        info (dict): A dict with keys as food ids and values as quantities 
        user_id: A unique identifier for the user who initiated the transaction
        record_id: A unique identifier for the record
    """

    def __init__(self, timestamp, info, user_id, record_id):
        self.timestamp = timestamp
        self.info = info
        self.user_id = user_id
        self.record_id = record_id

class RecordManager:
    def __init__(self):
        self._n_records = 0
        # Records is a dict with keys as ids and values as records. 
        self._records = dict()
        self._users_to_records = dict()

    def create_record(self, user_id, timestamp, info):
        # Use the total number of records created as id
        record_id = self._n_records         

        record = Record(timestamp, info, user_id, record_id)

        # Log record
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
                time_delta = (r_time - start_time).total_seconds()
                print("Time delta: ", time_delta)
                include = time_delta >= 0

            if end_time:
                time_delta = (end_time - r_time).total_seconds()
                print("Time delta: ", time_delta)

                include = include and (time_delta > 0)
            
            if not include:
                continue

            results[record_id] = record
        return results

    def remove_record(self, record_id):
        if record_id not in self._records:
            return
        
        record = self._records[record_id]
        
        user_id = record.user_id
        del self._users_to_records[user_id][record_id]

        del record

record_manager = RecordManager()

# TODO: Replace with session cookie (or perstient storage w/ login system)
userID = "John"

# TODO: Properly implement a food cache
food_cache = {} # Only need to store foods in log

# TODO: Revamp logging
# Each user is mapped to a dict with food ids as keys and quantites as values
daily_log = {userID: {}}
user_log = {userID: []}

# TODO: Storing previous search results in a global variable has many issues
# Proper asynchronous updates should be implemented using Ajax
search_results = [] # store search results to avoid repeated queries

# Get totals for user since timestamp
def get_totals(user_id, start_timestamp=None, end_timestamp=None):
    nutrient_types = ["calories", "fat", "carbs", "protein"]
    totals = {n: 0 for n in nutrient_types}
    
    print("Food cache: ", food_cache)
    log = {}
    records = record_manager.query_user_records(user_id, start_timestamp, end_timestamp)
    for record in records.values():
        for(f_id, quantity) in record.info.items():
            info = food_cache.get(f_id)
            if not info:
                continue

            for type in nutrient_types:
                totals[type] += quantity * info.get(type, 0)
            
            if f_id not in log:
                log[f_id] = 0
            log[f_id] += quantity

    return log, totals

# Extract the selected date from request;
# if a date is not selected, return the 
# current day
def get_selected_date(request):
    selected_date = request.args.get("date") or request.form.get("date")

    if selected_date is None:
        # Set selected date to start of current day
        now = datetime.now()
        day_start = datetime(now.year, now.month, now.day) 
        selected_date = day_start.date().isoformat()

    return selected_date

def update_food_cache(search_results):
    for result in search_results:
        id = int(result["fdc_id"])
        food_cache[id] = result 

def render_main(selected_date, extra_results=None):
    """Single helper so every route passes the same context."""

    print("Selected date: ", selected_date) 
            
    # start = datetime(selected_date.year, selected_date.month, selected_date.day)

    start = datetime.strptime(selected_date, "%Y-%m-%d")
    end = start + timedelta(days=1)

    daily_log, totals = get_totals(userID, start, end)

    print("Totals: ",  totals)
    print("Results: ", search_results)
    print("Daily log: ", daily_log)

    return render_template(
        'index.html',
        results=search_results,
        daily_log=daily_log,
        food_cache=food_cache,
        totals=totals,
        selected_date=selected_date
        )

@app.route("/")
def index():
    selected_date = get_selected_date(request)
    print("Selected date: ", selected_date)
    return render_main(selected_date)

@app.route('/handle_form', methods=['POST'])
def handle_form():
    global search_results
    user_input = request.form.get('query')
    search_results = search_food(user_input)
    update_food_cache(search_results)
    selected_date = get_selected_date(request)

    return render_main(selected_date)
    
@app.route('/update_log', methods=['POST'])
def update_log():
    print("Updating log")
    food_id = int(request.form.get('fdc_id'))
    quantity = int(request.form.get('quantity'))
    transaction_info = {food_id: quantity}
    
    selected_date = get_selected_date(request)

    # Create record of update
    time_stamp = datetime.strptime(selected_date, "%Y-%m-%d")

    # time_stamp = datetime.now()

    record_manager.create_record(userID, time_stamp, transaction_info) 
    print("Created record of update")
    
    if food_id not in daily_log[userID]:
        daily_log[userID][food_id] = 0
    daily_log[userID][food_id] = daily_log[userID].get(food_id, 0) + quantity
    
    print("Rendering")

    return render_main(selected_date)

# TODO: Fix deletion
@app.route('/delete_log', methods=['POST'])
def delete_log():
    food_id = int(request.form.get('fdc_id'))
    daily_log[userID].pop(food_id, None)
    selected_date = get_selected_date(request)

    return render_main(selected_date)
