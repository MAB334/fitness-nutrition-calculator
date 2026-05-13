import unittest

from nutrition_app.db.catalog import FoodRecord
from nutrition_app.schemas.api import BulkResolveRequest, DaySummaryRequest
from nutrition_app.services.nutrition import NutritionService, estimate_targets


class StubCatalog:
    def __init__(self, foods):
        self.foods = foods

    def get_food(self, source, source_food_id):
        return self.foods.get((source, source_food_id))

    def search_foods(self, query, limit=20):
        lowered = query.lower()
        results = []
        for food in self.foods.values():
            haystacks = [food.name.lower()]
            if food.alias_name:
                haystacks.append(food.alias_name.lower())
            if food.brand:
                haystacks.append(food.brand.lower())
            if any(lowered in haystack for haystack in haystacks):
                results.append(food)
        return results[:limit]


class NutritionServiceTests(unittest.TestCase):
    def setUp(self):
        self.foods = {
            ("chinanutri_fq", "chicken"): FoodRecord(
                source="chinanutri_fq",
                source_food_id="chicken",
                name="鸡胸肉",
                alias_name=None,
                brand=None,
                category_top="肉类",
                category_sub=None,
                food_type="basic_food",
                energy_kcal_100g=165.0,
                protein_g_100g=31.0,
                fat_g_100g=3.6,
                carb_g_100g=0.0,
                fiber_g_100g=0.0,
                sodium_mg_100g=74.0,
                detail_url=None,
            ),
            ("chinanutri_fq", "rice"): FoodRecord(
                source="chinanutri_fq",
                source_food_id="rice",
                name="白米饭",
                alias_name=None,
                brand=None,
                category_top="谷物",
                category_sub=None,
                food_type="basic_food",
                energy_kcal_100g=116.0,
                protein_g_100g=2.6,
                fat_g_100g=0.3,
                carb_g_100g=25.9,
                fiber_g_100g=0.3,
                sodium_mg_100g=2.0,
                detail_url=None,
            ),
            ("chinanutri_fq", "oats"): FoodRecord(
                source="chinanutri_fq",
                source_food_id="oats",
                name="燕麦片",
                alias_name=None,
                brand=None,
                category_top="谷物",
                category_sub=None,
                food_type="basic_food",
                energy_kcal_100g=389.0,
                protein_g_100g=16.9,
                fat_g_100g=6.9,
                carb_g_100g=66.3,
                fiber_g_100g=10.6,
                sodium_mg_100g=2.0,
                detail_url=None,
            ),
        }
        self.service = NutritionService(StubCatalog(self.foods))

    def test_estimate_targets_has_positive_values(self):
        profile = DaySummaryRequest.model_validate(
            {
                "profile": {
                    "sex": "male",
                    "age": 30,
                    "height_cm": 180,
                    "weight_kg": 80,
                    "activity_level": "moderate",
                    "goal": "maintain",
                },
                "entries": [],
            }
        ).profile
        targets = estimate_targets(profile)
        self.assertGreater(targets["target_kcal"], 2000)
        self.assertGreater(targets["target_protein_g"], 100)
        self.assertGreater(targets["target_carb_g"], 100)

    def test_day_summary_scales_foods_by_portions(self):
        request = DaySummaryRequest.model_validate(
            {
                "profile": {
                    "sex": "male",
                    "age": 30,
                    "height_cm": 180,
                    "weight_kg": 80,
                    "activity_level": "moderate",
                    "goal": "maintain",
                },
                "entries": [
                    {
                        "entry_id": "lunch-chicken",
                        "meal_type": "lunch",
                        "source": "chinanutri_fq",
                        "source_food_id": "chicken",
                        "quantity": 1,
                        "unit_key": "serving",
                        "unit_label": "份",
                    },
                    {
                        "entry_id": "lunch-rice",
                        "meal_type": "lunch",
                        "source": "chinanutri_fq",
                        "source_food_id": "rice",
                        "quantity": 1,
                        "unit_key": "bowl",
                        "unit_label": "碗",
                    },
                ],
            }
        )
        summary = self.service.build_day_summary(request)
        self.assertAlmostEqual(summary["totals"]["kcal"], 372.0, places=1)
        self.assertAlmostEqual(summary["totals"]["protein_g"], 41.1, places=1)
        self.assertAlmostEqual(summary["totals"]["fat_g"], 4.8, places=1)
        self.assertAlmostEqual(summary["totals"]["carb_g"], 38.9, places=1)
        lunch = next(item for item in summary["meals"] if item["meal_type"] == "lunch")
        self.assertEqual(len(lunch["entries"]), 2)
        self.assertEqual(lunch["entries"][0]["entry_id"], "lunch-chicken")
        self.assertEqual(lunch["entries"][0]["unit_label"], "份")

    def test_bulk_resolve_parses_multiple_lines(self):
        payload = BulkResolveRequest.model_validate(
            {
                "text": "早餐 鸡胸肉 1份\n燕麦 2碗\n晚餐 米饭 1碗\n坏数据",
                "default_meal_type": "lunch",
            }
        )
        resolved = self.service.resolve_bulk_entries(payload)
        self.assertEqual(len(resolved["resolved"]), 3)
        self.assertEqual(len(resolved["unresolved"]), 1)
        self.assertEqual(resolved["resolved"][0]["meal_type"], "breakfast")
        self.assertEqual(resolved["resolved"][1]["meal_type"], "lunch")
        self.assertEqual(resolved["resolved"][2]["meal_type"], "dinner")
        self.assertEqual(resolved["resolved"][0]["unit_label"], "份")
        self.assertEqual(resolved["resolved"][1]["unit_label"], "碗")

    def test_bulk_resolve_supports_chinese_quantity_words(self):
        payload = BulkResolveRequest.model_validate(
            {
                "text": "早餐鸡胸肉两份\n燕麦 半碗\n晚餐 米饭 壹碗",
                "default_meal_type": "lunch",
            }
        )
        resolved = self.service.resolve_bulk_entries(payload)
        self.assertEqual(len(resolved["resolved"]), 3)
        self.assertEqual(resolved["resolved"][0]["quantity"], 2.0)
        self.assertEqual(resolved["resolved"][1]["quantity"], 0.5)
        self.assertEqual(resolved["resolved"][2]["quantity"], 1.0)
        self.assertEqual(resolved["resolved"][0]["grams"], 240.0)
        self.assertEqual(resolved["resolved"][1]["grams"], 20.0)
        self.assertEqual(resolved["resolved"][2]["grams"], 150.0)


if __name__ == "__main__":
    unittest.main()
