import os
from pathlib import Path

from dotenv import load_dotenv
from usda_fdc import FdcClient, FdcApiError, FdcAuthError

from ml.ml_utils import deduplicate_foods

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / ".env")
API_KEY = os.getenv("FDC_API_KEY")

client = FdcClient(API_KEY)


def extract_nutrients(food):
    """
    Extract key nutrients from FDC food object.
    """
    nutrients = {
        "calories": None,
        "protein": None,
        "fat": None,
        "carbs": None
    }

    for nutrient in food.nutrients:
        name = nutrient.name.lower()

        if "energy" in name:
            nutrients["calories"] = nutrient.amount
        elif "protein" in name:
            nutrients["protein"] = nutrient.amount
        elif "fat" in name:
            nutrients["fat"] = nutrient.amount
        elif "carbohydrate" in name:
            nutrients["carbs"] = nutrient.amount

    return nutrients


def search_food(query: str):
    """
    Search foods using USDA FDC client and return structured results.
    """
    try:
        results = client.search(query)

        foods = []

        # Fetch more candidates than needed so deduplication has room to work
        for food_item in results.foods[:20]:
            try:
                # get full food details (nutrients not always complete in search results)
                food = client.get_food(food_item.fdc_id)

                nutrients = extract_nutrients(food)

                foods.append({
                    "name": food.description,
                    "fdc_id": food.fdc_id,
                    **nutrients
                })

            except Exception:
                continue  # skip bad entries safely

        # Remove near-duplicate descriptions, keep most nutrient-complete entry
        foods = deduplicate_foods(foods)
 
        return foods[:5]

    except FdcAuthError as e:
        print(f"Auth error: {e}")
        return []
    except FdcApiError as e:
        print(f"API error: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []