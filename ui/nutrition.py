from flask import Flask, request, render_template
from nutrition_api import search_food

app = Flask(__name__)

# TODO: Replace with session cookie (or perstient storage w/ login system)
userID = "John"

# TODO: Properly implement a food cache
food_cache = {} # Only need to store foods in log

# TODO: Revamp logging
# Each user is mapped to a dict with food ids as keys and quantites as values
daily_log = {userID: {}} 

# TODO: Storing previous search results in a global variable has many issues
# Proper asynchronous updates should be implemented using Ajax
search_results = [] # store search results to avoid repeated queries

def get_daily_totals():
    nutrient_types = ["calories", "fat", "carbs", "protein"]
    totals = {n: 0 for n in nutrient_types}
    for f_id, quantity in daily_log[userID].items():
        print("Food cache: ", food_cache)
        info = food_cache[f_id]

        for type in nutrient_types:
            if type in info:
                totals[type] += quantity * info[type]

    return totals

def update_food_cache(search_results):
    for result in search_results:
        id = result["fdc_id"]
        food_cache[id] = result 

@app.route("/")
def index():
    return render_template('index.html')

@app.route('/handle_form', methods=['POST'])
def handle_form():
    user_input = request.form.get('query')
    search_results = search_food(user_input)
    update_food_cache(search_results)

    return render_template('search.html', results=search_results, totals=get_daily_totals()) 
    
@app.route('/update_log', methods=['POST'])
def update_log():
    food_id = int(request.form.get('fdc_id'))
    quantity = int(request.form.get('quantity'))

    if food_id not in daily_log[userID]:
        daily_log[userID][food_id] = 0
    daily_log[userID][food_id] += quantity

    return render_template('search.html', results=search_results, totals=get_daily_totals()) 

@app.route('/search')
def search():
    return render_template('search.html', results=search_food(), totals=get_daily_totals()) 