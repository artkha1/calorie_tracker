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
        {"name": "Chicken broiled usda", "calories": 165, "protein": 31, "fat": 4, "carbs": 0},
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

from ui.ui import get_totals, compute_goal_stats, DEFAULT_GOALS
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
    with patch("ui.ui.food_cache", FOOD_CACHE):
        log, totals = get_totals(records)
    assert log[1001] == 2
    assert totals["calories"] == pytest.approx(300)
    assert totals["protein"] == pytest.approx(10)


def test_get_totals_multiple_foods():
    records = OrderedDict({1: _make_record({1001: 1, 1002: 2})})
    with patch("ui.ui.food_cache", FOOD_CACHE):
        log, totals = get_totals(records)
    assert totals["calories"] == pytest.approx(150 + 140)  # 1×150 + 2×70
    assert totals["protein"] == pytest.approx(5 + 12)


def test_get_totals_skips_unknown_food():
    records = OrderedDict({1: _make_record({9999: 1})})  # not in cache
    with patch("ui.ui.food_cache", FOOD_CACHE):
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