import pytest
from collections import OrderedDict
from datetime import datetime
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ---------------------------------------------------------------------------
# ml_utils tests
# ---------------------------------------------------------------------------

from ml.ml_utils import deduplicate_foods


def test_deduplicate_foods_empty():
    assert deduplicate_foods([]) == []


def test_deduplicate_foods_single():
    food = {"name": "Apple", "calories": 95, "protein": 0.5, "fat": 0.3, "carbs": 25}
    assert deduplicate_foods([food]) == [food]


def test_deduplicate_foods_removes_near_duplicates():
    foods = [
        {"name": "Chicken broiled", "calories": 165, "protein": 31, "fat": 4, "carbs": 0},
        {"name": "Chicken BROILED", "calories": 165, "protein": 31, "fat": 4, "carbs": 0},
        {"name": "Salmon fillet baked", "calories": 208, "protein": 20, "fat": 13, "carbs": 0},
    ]
    result = deduplicate_foods(foods)
    names = [f["name"] for f in result]
    # The two chicken entries should collapse to one; salmon is distinct
    assert len(result) == 2
    assert any("salmon" in n.lower() for n in names)


def test_deduplicate_foods_keeps_most_complete():
    # Second entry has more non-None values — it should be preferred
    foods = [
        {"name": "Brown rice cooked", "calories": 216, "protein": None, "fat": None, "carbs": 45},
        {"name": "Brown rice cooked", "calories": 216, "protein": 5, "fat": 2, "carbs": 45},
    ]
    result = deduplicate_foods(foods)
    assert len(result) == 1
    assert result[0]["protein"] == 5


def test_deduplicate_foods_keeps_distinct_items():
    foods = [
        {"name": "Apple raw", "calories": 95, "protein": 0.5, "fat": 0.3, "carbs": 25},
        {"name": "Banana raw", "calories": 105, "protein": 1.3, "fat": 0.4, "carbs": 27},
        {"name": "Orange raw", "calories": 62, "protein": 1.2, "fat": 0.2, "carbs": 15},
    ]
    result = deduplicate_foods(foods)
    assert len(result) == 3


# ---------------------------------------------------------------------------
# ui helper tests (no Flask app or DB needed)
# ---------------------------------------------------------------------------

from app.helpers import get_totals, compute_goal_stats
from app.config import DEFAULT_GOALS
from storage.database import Record


def _make_record(info, ts=None):
    return Record(
        timestamp=ts or datetime(2024, 1, 1, 12, 0),
        info=info,
        user_id="testuser",
        record_id=1,
    )


FOOD_CACHE = {
    1001: {"name": "Oats", "calories": 150, "protein": 5, "fat": 3, "carbs": 27},
    1002: {"name": "Eggs", "calories": 70,  "protein": 6, "fat": 5, "carbs": 1},
}


def test_get_totals_empty():
    log, totals = get_totals(OrderedDict())
    assert log == {}
    assert all(v == 0 for v in totals.values())


def test_get_totals_single_food():
    records = OrderedDict({1: _make_record({1001: 2})})  # 2 servings of oats
    with patch("app.state.food_cache", FOOD_CACHE):
        log, totals = get_totals(records)
    assert log[1001] == 2
    assert totals["calories"] == pytest.approx(300)
    assert totals["protein"] == pytest.approx(10)


def test_get_totals_multiple_foods():
    records = OrderedDict({1: _make_record({1001: 1, 1002: 2})})
    with patch("app.state.food_cache", FOOD_CACHE):
        log, totals = get_totals(records)
    assert totals["calories"] == pytest.approx(150 + 140)  # 1×150 + 2×70
    assert totals["protein"] == pytest.approx(5 + 12)


def test_get_totals_skips_unknown_food():
    records = OrderedDict({1: _make_record({9999: 1})})  # not in cache
    with patch("app.state.food_cache", FOOD_CACHE):
        log, totals = get_totals(records)
    assert 9999 not in log
    assert totals["calories"] == 0


def test_compute_goal_stats_under_goal():
    totals = {"calories": 1500, "protein": 40, "fat": 50, "carbs": 200}
    stats = compute_goal_stats(totals, DEFAULT_GOALS)
    assert stats["calories"]["consumed"] == 1500
    assert stats["calories"]["remaining"] == 500
    assert stats["calories"]["over"] == 0
    assert stats["calories"]["progress"] == 75.0


def test_compute_goal_stats_over_goal():
    totals = {"calories": 2500, "protein": 40, "fat": 50, "carbs": 200}
    stats = compute_goal_stats(totals, DEFAULT_GOALS)
    assert stats["calories"]["over"] == 500
    assert stats["calories"]["remaining"] == 0
    assert stats["calories"]["progress"] == 100.0


def test_compute_goal_stats_exactly_at_goal():
    totals = dict(DEFAULT_GOALS)
    stats = compute_goal_stats(totals, DEFAULT_GOALS)
    for macro in DEFAULT_GOALS:
        assert stats[macro]["remaining"] == 0
        assert stats[macro]["over"] == 0
        assert stats[macro]["progress"] == 100.0


# ---------------------------------------------------------------------------
# nl_parser tests
# ---------------------------------------------------------------------------

from api.nl_parser import is_natural_language, parse_food_input


class TestIsNaturalLanguage:
    def test_single_word_is_not_nl(self):
        assert is_natural_language("apple") is False

    def test_two_words_is_nl(self):
        assert is_natural_language("chicken breast") is True

    def test_starts_with_digit_is_nl(self):
        assert is_natural_language("2 eggs") is True

    def test_single_digit_word_is_nl(self):
        assert is_natural_language("3 oranges") is True

    def test_full_sentence_is_nl(self):
        assert is_natural_language("2 eggs and a slice of toast") is True

    def test_empty_string_is_not_nl(self):
        assert is_natural_language("") is False

    def test_whitespace_only_is_not_nl(self):
        assert is_natural_language("   ") is False


class TestParseFoodInput:
    """All tests mock the Gemini API — no network calls, no API key needed."""

    def _make_mock_model(self, response_text):
        """Return a mock that mimics the google-genai Client."""
        mock_response = MagicMock()
        mock_response.text = response_text
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        return mock_client

    def test_basic_parse(self):
        mock_model = self._make_mock_model(
            '[{"food": "egg", "quantity": 2}, {"food": "toast", "quantity": 1}]'
        )
        with patch("api.nl_parser._get_model", return_value=mock_model):
            result = parse_food_input("2 eggs and a toast")
        assert result == [
            {"food": "egg", "quantity": 2.0},
            {"food": "toast", "quantity": 1.0},
        ]

    def test_quantity_is_float(self):
        mock_model = self._make_mock_model(
            '[{"food": "oatmeal", "quantity": 0.5}]'
        )
        with patch("api.nl_parser._get_model", return_value=mock_model):
            result = parse_food_input("half a cup of oatmeal")
        assert result[0]["quantity"] == 0.5

    def test_strips_markdown_fences(self):
        mock_model = self._make_mock_model(
            '```json\n[{"food": "banana", "quantity": 1}]\n```'
        )
        with patch("api.nl_parser._get_model", return_value=mock_model):
            result = parse_food_input("a banana")
        assert result == [{"food": "banana", "quantity": 1.0}]

    def test_returns_none_on_invalid_json(self):
        mock_model = self._make_mock_model("not valid json at all")
        with patch("api.nl_parser._get_model", return_value=mock_model):
            result = parse_food_input("something")
        assert result is None

    def test_returns_none_when_no_api_key(self):
        with patch("api.nl_parser._get_model", return_value=None):
            result = parse_food_input("2 eggs and toast")
        assert result is None

    def test_returns_none_on_non_list_response(self):
        mock_model = self._make_mock_model('{"food": "egg", "quantity": 2}')
        with patch("api.nl_parser._get_model", return_value=mock_model):
            result = parse_food_input("2 eggs")
        assert result is None

    def test_skips_malformed_items(self):
        # One valid item, one missing 'quantity' — only valid one returned
        mock_model = self._make_mock_model(
            '[{"food": "egg", "quantity": 2}, {"food": "toast"}]'
        )
        with patch("api.nl_parser._get_model", return_value=mock_model):
            result = parse_food_input("2 eggs and toast")
        assert result == [{"food": "egg", "quantity": 2.0}]

    def test_multiple_items(self):
        mock_model = self._make_mock_model(
            '[{"food": "pizza slice", "quantity": 3}, '
            '{"food": "cola", "quantity": 1}]'
        )
        with patch("api.nl_parser._get_model", return_value=mock_model):
            result = parse_food_input("3 slices of pizza and a coke")
        assert len(result) == 2
        assert result[0] == {"food": "pizza slice", "quantity": 3.0}
        assert result[1] == {"food": "cola", "quantity": 1.0}

    def test_returns_none_on_api_exception(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("network error")
        with patch("api.nl_parser._get_model", return_value=mock_client):
            result = parse_food_input("2 eggs")
        assert result is None