from flask import Flask, request, render_template
from api.nutrition_api import search_food
from collections import OrderedDict
from datetime import datetime, timedelta

app = Flask(__name__)

macro_types = ["calories", "fat", "carbs", "protein"]
macro_units = {"calories": "",
         "fat": "g",
         "carbs": "g",
         "protein": "g"}

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
                time_delta = (r_time - start_time).total_seconds()
                include = time_delta >= 0

            if end_time:
                time_delta = (end_time - r_time).total_seconds()
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
def get_totals(records):

    # Initalize dict to hold nutrition totals
    totals = {n: 0 for n in macro_types}
    
    log = {}

    for record in records.values():
        for(f_id, quantity) in record.info.items():
            # Get nutrition data for food id f_id
            info = food_cache.get(f_id)

            # Skip record if there is no data for food id
            if not info:
                continue
            
            # Update nutrition totals 
            for type in macro_types:
                if type not in info:
                    continue
                
                if info.get(type, 0) is None:
                    continue
                
                totals[type] += quantity * info.get(type, 0)
            
            # 
            if f_id not in log:
                log[f_id] = 0
             
            # Update food_id quantaity
            log[f_id] += quantity

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
        id = int(result["fdc_id"])
        food_cache[id] = result 

def render_main(start_date, end_date, extra_results=None):
    """Single helper so every route passes the same context."""
    
    # Parse selected date (assume start of day)
    start = datetime.strptime(start_date, "%Y-%m-%d")
    
    # Get nutritional information for the day
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    # Get all records for user between start time stamp and end time stamp
    records = record_manager.query_user_records(userID, start, end)

    # Get totals for records
    log, totals = get_totals(records)

    curr_time = datetime.now()
    curr_time = curr_time.strftime("%Y-%m-%d %H:%M:%S")
    
    """
    print("Selected date: ", selected_date) 
    print("Totals: ",  totals)
    print("Results: ", search_results)
    print("Daily log: ", daily_log)
    """

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
        macro_units=macro_units
        )

@app.route("/")
def index():
    start_date, end_date = get_selected_dates(request)
    return render_main(start_date, end_date)

@app.route('/handle_form', methods=['POST'])
def handle_form():
    global search_results
    user_input = request.form.get('query')
    search_results = search_food(user_input)
    update_food_cache(search_results)
    start_date, end_date = get_selected_dates(request)

    return render_main(start_date, end_date)
    
# TODO: Support multiple types of foods in record
@app.route('/update_log', methods=['POST'])
def update_log():
    food_id = int(request.form.get('fdc_id'))
    quantity = int(request.form.get('quantity'))

    # Create timestamp from logged time
    t = request.form.get('time')
    time_stamp = datetime.strptime(t, "%Y-%m-%dT%H:%M:%S")
    
    transaction_info = {food_id: quantity}
    
    # Create record of update
    record_manager.create_record(userID, time_stamp, transaction_info) 

    start_date, end_date = get_selected_dates(request)
    return render_main(start_date, end_date)

@app.route('/delete_log', methods=['POST'])
def delete_log():
    # Remove record
    record_id = int(request.form.get('record_id'))
    record_manager.remove_record(record_id)

    start_date, end_date = get_selected_dates(request)
    return render_main(start_date, end_date)
