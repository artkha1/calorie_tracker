"""
Application-wide constants.
Centralised here so routes, helpers, and tests all import from one place.
"""

MACRO_TYPES = ["calories", "fat", "carbs", "protein"]

MACRO_UNITS = {
    "calories": "",
    "fat": "g",
    "carbs": "g",
    "protein": "g",
}

DEFAULT_GOALS = {
    "calories": 2000,
    "protein": 50,
    "carbs": 275,
    "fat": 78,
}