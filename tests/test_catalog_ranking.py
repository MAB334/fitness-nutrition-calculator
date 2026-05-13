import unittest

from nutrition_app.db.catalog import FoodRecord, build_search_sort_key, expand_query_terms, normalize_search_text, search_virtual_food_records


class CatalogRankingTests(unittest.TestCase):
    def test_expand_query_terms_adds_common_food_aliases(self):
        self.assertIn("鸡胸脯肉", expand_query_terms("鸡胸肉"))
        self.assertIn("鸡胸脯肉", expand_query_terms("鸡胸"))
        self.assertIn("燕麦片", expand_query_terms("燕麦"))

    def test_basic_food_beats_processed_packaged_for_generic_query(self):
        query = normalize_search_text("鸡胸肉")
        terms = expand_query_terms(query)
        basic_food = FoodRecord(
            source="chinanutri_fq",
            source_food_id="basic-chicken",
            name="鸡胸脯肉",
            alias_name=None,
            brand=None,
            category_top="禽肉类",
            category_sub="生鲜",
            food_type="basic_food",
            energy_kcal_100g=133.0,
            protein_g_100g=19.4,
            fat_g_100g=5.0,
            carb_g_100g=0.0,
            fiber_g_100g=0.0,
            sodium_mg_100g=50.0,
            detail_url=None,
        )
        processed_packaged = FoodRecord(
            source="chinanutri_nlc",
            source_food_id="packaged-chicken",
            name="鸡胸肉干（黑椒味）",
            alias_name=None,
            brand="某品牌",
            category_top="熟肉干制品",
            category_sub="90g",
            food_type="packaged_food",
            energy_kcal_100g=300.0,
            protein_g_100g=35.0,
            fat_g_100g=8.0,
            carb_g_100g=20.0,
            fiber_g_100g=None,
            sodium_mg_100g=1200.0,
            detail_url=None,
        )
        self.assertLess(
            build_search_sort_key(basic_food, query, terms),
            build_search_sort_key(processed_packaged, query, terms),
        )

    def test_exact_packaged_match_stays_ahead_when_query_is_specific(self):
        query = normalize_search_text("鸡胸肉干")
        terms = expand_query_terms(query)
        exact_packaged = FoodRecord(
            source="chinanutri_nlc",
            source_food_id="packaged-chicken",
            name="鸡胸肉干",
            alias_name=None,
            brand="某品牌",
            category_top="熟肉干制品",
            category_sub="90g",
            food_type="packaged_food",
            energy_kcal_100g=300.0,
            protein_g_100g=35.0,
            fat_g_100g=8.0,
            carb_g_100g=20.0,
            fiber_g_100g=None,
            sodium_mg_100g=1200.0,
            detail_url=None,
        )
        generic_basic = FoodRecord(
            source="chinanutri_fq",
            source_food_id="basic-chicken",
            name="鸡胸脯肉",
            alias_name="鸡胸肉",
            brand=None,
            category_top="禽肉类",
            category_sub="生鲜",
            food_type="basic_food",
            energy_kcal_100g=133.0,
            protein_g_100g=19.4,
            fat_g_100g=5.0,
            carb_g_100g=0.0,
            fiber_g_100g=0.0,
            sodium_mg_100g=50.0,
            detail_url=None,
        )
        self.assertLess(
            build_search_sort_key(exact_packaged, query, terms),
            build_search_sort_key(generic_basic, query, terms),
        )


    def test_virtual_recipe_search_matches_common_home_dishes(self):
        results = search_virtual_food_records("西红柿炒蛋", limit=3)
        self.assertTrue(results)
        self.assertEqual(results[0].source, "virtual_recipe")
        self.assertEqual(results[0].name, "番茄炒蛋")


if __name__ == "__main__":
    unittest.main()
