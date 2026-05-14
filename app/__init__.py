"""
Application factory.

Usage:
    from app import create_app
    app = create_app()

Using the factory pattern means the app object isn't created at import time,
which makes testing easier (you can pass different configs) and is standard
Flask practice.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-not-for-prod")

    # Initialise database (creates tables if they don't exist)
    from storage.database import init_db
    init_db()

    # Seed the in-memory food cache from the DB
    from storage.database import load_food_cache
    from app import state
    state.food_cache.update(load_food_cache())

    # Register blueprints
    from app.auth.auth import bp as auth_bp
    from app.routes import bp as main_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    return app