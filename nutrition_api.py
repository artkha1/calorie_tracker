from usda_fdc import FdcClient, FdcApiError, FdcAuthError
import os
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()
API_KEY = os.getenv("FDC_API_KEY")
print(API_KEY)

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

        # limit results for UI simplicity
        for food_item in results.foods[:5]:
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

        return foods

    except FdcAuthError as e:
        print(f"Auth error: {e}")
        return []
    except FdcApiError as e:
        print(f"API error: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []