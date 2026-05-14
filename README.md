# Calorie Tracker

A web-based calorie tracking application built with Flask. Search for foods using the USDA FoodData Central database, log meals with natural language ("2 eggs and a slice of toast"), and track daily macro goals.

**[Live demo →](https://calorie-tracker-ncz7.onrender.com/)** *(may take ~30s to wake from sleep on free tier)*

![CI](https://github.com/artkha1/calorie_tracker/actions/workflows/ci.yml/badge.svg)

---

## Features

- **Natural language food logging** — type "2 eggs and a white toast with bacon" and the app uses the Gemini AI API to parse it into individual items, looks each one up in parallel, and logs them automatically with the correct quantities
- **USDA FoodData Central search** — 600,000+ foods with full macro breakdown
- **Daily macro goals** — set custom calorie, protein, carb, and fat targets with visual progress bars
- **Date navigation** — browse and review logs for any past day
- **User accounts** — register, log in, and keep your data private

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Database | SQLite (via stdlib `sqlite3`) |
| AI parsing | Google Gemini 2.5 Flash API |
| Nutrition data | USDA FoodData Central API |
| Deployment | Render (free tier) |
| CI/CD | GitHub Actions |

## Project structure

```
main.py               # entry point — creates and runs the Flask app
app/
    __init__.py       # create_app() factory — registers blueprints, seeds cache
    config.py         # constants (macro types, default goals)
    helpers.py        # pure business logic (totals, goal stats, cache updates)
    routes.py         # all HTTP route handlers
    state.py          # in-memory server state (food cache, selections)
    auth/
        auth.py       # auth blueprint (login, register, logout)
    templates/
        index.html    # single-page Jinja2 template
api/
    nutrition_api.py  # USDA FoodData Central wrapper
    nl_parser.py      # Gemini-powered natural language food parser
storage/
    database.py       # SQLite layer (users, records, food cache, goals)
ml/
    ml_utils.py       # food deduplication using cosine similarity
tests/
    test_all.py          # pytest suite (unit tests, all external APIs mocked)
```

## Local setup

**1. Clone and create a virtual environment**

```bash
git clone https://github.com/artkha1/calorie_tracker.git
cd calorie_tracker
python -m venv venv

# Mac/Linux
source venv/bin/activate
# Windows
venv\Scripts\activate
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Set up environment variables**

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Where to get it |
|---|---|
| `FDC_API_KEY` | [fdc.nal.usda.gov/api-guide](https://fdc.nal.usda.gov/api-guide) — free, no credit card |
| `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — free, no credit card |
| `FLASK_SECRET_KEY` | Any random string: `python -c "import secrets; print(secrets.token_hex(32))"` |

**4. Run**

```bash
python main.py
```

The app will be available at `http://localhost:5000`.

## Running tests

```bash
pytest tests/ -v
```

All external API calls (Gemini, FDC) are mocked — tests run offline with no API keys needed.

## Deployment

The app is configured for [Render](https://render.com) via `render.yaml`. To deploy your own instance:

1. Fork the repo
2. Sign up at render.com → New → Web Service → connect your fork
3. Render will detect `render.yaml` and pre-fill all settings
4. Set `FDC_API_KEY` and `GEMINI_API_KEY` in the Render dashboard under Environment
5. Copy the deploy hook URL from Render into a GitHub secret named `RENDER_DEPLOY_HOOK`

Every push to `main` will run the test suite via GitHub Actions and, if tests pass, trigger a redeploy automatically.

> **Note:** The free Render tier uses an ephemeral filesystem — the SQLite database resets on each redeploy or restart. This is fine for a demo; for persistent storage, swap to Render's free Postgres or a hosted SQLite service like Turso.

## Room for Improvement
The USDA FDC API is, to put it simply, not the most accurate. There is no way to specify the serving size, and their methodology is questionable (the search result "blueberry" may be listed as having 250 calories, an equivalent of 3 cups). This is a proof of concept demo project, so data quality was not prioritized. Unfortunately, for now, it can't be used as a genuinely helpful nutrition tracker, but it is a potential area of improvement for the future.

## Acknowledgements
The core of this project was originally developed for CS 222 (Software Design Lab) at the University of Illinois at Urbana-Champaign with contributions from Yassir Atlas (UI, Record and Log Management), Martin Gospodinov (User Auth, Cloud Storage, originally on Supabase), and Leo Penn (UI, Database Design).