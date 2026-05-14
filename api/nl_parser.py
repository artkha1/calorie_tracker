"""
Natural language food input parser.

Converts free-form text like "2 eggs and a slice of toast" into a structured
list of (food_name, quantity) pairs that can be passed to the FDC search API.

Uses the Gemini API (free tier, no credit card required).
Get a key at: https://aistudio.google.com/apikey
"""

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / ".env")

# Lazy-initialised so the app still starts if the key is missing —
# the parser will just return None and the caller falls back to plain search.
_model = None


def _get_model():
    global _model
    if _model is None:
        import google.genai as genai
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            return None
        _model = genai.Client(api_key=api_key)
    return _model


_SYSTEM = """You are a food quantity parser. Given a natural language description
of food, return ONLY a JSON array. Each element must have:
  "food": singular food name as a short search-friendly string (e.g. "egg", "white toast")
  "quantity": numeric quantity as a number

Rules:
- "a" / "an" / "one" → 1
- "couple" / "a few" → 2
- Always use singular food names
- Split combined items into separate entries
- Return ONLY the JSON array, no markdown, no explanation

Examples:
"2 eggs and a toast" → [{"food":"egg","quantity":2},{"food":"toast","quantity":1}]
"bowl of oatmeal with some blueberries" → [{"food":"oatmeal","quantity":1},{"food":"blueberry","quantity":1}]
"three slices of pizza" → [{"food":"pizza slice","quantity":3}]
"""


def is_natural_language(query: str) -> bool:
    """
    Heuristic: treat the query as natural language if it contains more than
    one word OR starts with a digit (e.g. "2 eggs").  Single bare words like
    "apple" or "chicken" go straight to FDC without burning an API call.
    """
    query = query.strip()
    if re.match(r"^\d", query):
        return True
    return len(query.split()) > 1


def parse_food_input(query: str) -> list[dict] | None:
    """
    Parse a natural language food description into structured items.

    Returns a list of dicts: [{"food": str, "quantity": int/float}, ...]
    Returns None if parsing fails or the API key is not configured, so the
    caller can fall back to treating the raw query as a direct FDC search.
    """

    try:
        client = _get_model()
        if client is None:
            return None
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{_SYSTEM}\n\nInput: {query}",
        )
        text = response.text.strip()

        # Strip any accidental markdown fences the model might add
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

        items = json.loads(text)

        # Validate shape — must be a list of dicts with the right keys
        if not isinstance(items, list):
            return None
        validated = []
        for item in items:
            if isinstance(item, dict) and "food" in item and "quantity" in item:
                validated.append({
                    "food": str(item["food"]),
                    "quantity": float(item["quantity"]),
                })
        return validated if validated else None

    except Exception as e:
        print(f"[nl_parser] parse error: {e}")
        return None