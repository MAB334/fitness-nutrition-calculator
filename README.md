# Nutrition Database Builder

This project builds local nutrition datasets for a calorie and macro tracking app.

Current source families:

- China CDC food composition query platform
- China CDC packaged-food nutrition label query platform
- FatSecret China public food directory
- USDA FoodData Central full CSV export
- Open Food Facts CSV export

China-focused output layout:

- default storage root: `E:\爬虫抓包数据\china`
- raw food-composition pages: `E:\爬虫抓包数据\china\raw\chinanutri_fq`
- raw packaged-food pages: `E:\爬虫抓包数据\china\raw\chinanutri_nlc`
- raw FatSecret pages: `E:\爬虫抓包数据\china\raw\fatsecret_cn`
- processed SQLite database: `E:\爬虫抓包数据\china\processed\china_nutrition.db`
- crawl stats: `E:\爬虫抓包数据\china\processed\china_stats.json`

China-focused crawler:

```bash
python scripts/build_china_nutrition_db.py crawl-fq
python scripts/build_china_nutrition_db.py crawl-nlc --max-pages 20 --detail-workers 4
python scripts/build_china_nutrition_db.py crawl-fatsecret --skip-brands --target-total-records 100000 --max-keyword-terms 1200 --detail-limit 1500
python scripts/build_china_nutrition_db.py crawl-fatsecret --skip-brands --keyword-terms-file config/personal_fatsecret_terms.txt --skip-derived-keywords --max-search-pages-per-brand 40
python scripts/build_china_nutrition_db.py stats
```

US / international builder:

```bash
python scripts/build_nutrition_db.py build --download --sources usda_full_csv
python scripts/build_nutrition_db.py stats
```

Notes:

- The China-focused crawler can be relocated with `CHINA_NUTRITION_DATA_ROOT`.
- For packaged-food crawling, `--detail-workers 4` is a reasonable speed setting.
- For large market-product expansion, `crawl-fatsecret --skip-brands` is the faster discovery mode.
- For personal-use targeted expansion, use `config/personal_fatsecret_terms.txt` with `--keyword-terms-file` and `--skip-derived-keywords`.
- The US / international builder no longer defaults to USDA. You must pass `--sources` explicitly.
