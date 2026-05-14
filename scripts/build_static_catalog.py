from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "nutrition_app" / "data" / "china_nutrition.db"
OUTPUT_PATH = REPO_ROOT / "nutrition_app" / "static" / "data" / "catalog.min.json"

FIELDS = [
    "source",
    "source_food_id",
    "name",
    "alias_name",
    "brand",
    "category_top",
    "category_sub",
    "food_type",
    "energy_kcal_100g",
    "protein_g_100g",
    "fat_g_100g",
    "carb_g_100g",
    "fiber_g_100g",
    "sodium_mg_100g",
]

SQL = f"""
SELECT
    source,
    source_food_id,
    name,
    alias_name,
    brand,
    category_top,
    category_sub,
    food_type,
    energy_kcal_100g,
    protein_g_100g,
    fat_g_100g,
    carb_g_100g,
    fiber_g_100g,
    sodium_mg_100g
FROM china_food_catalog
WHERE
    energy_kcal_100g IS NOT NULL
    AND protein_g_100g IS NOT NULL
    AND fat_g_100g IS NOT NULL
    AND carb_g_100g IS NOT NULL
ORDER BY
    CASE food_type
        WHEN 'basic_food' THEN 0
        WHEN 'packaged_food' THEN 1
        ELSE 2
    END,
    protein_g_100g DESC,
    name ASC
"""


def main() -> int:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Bundled database not found: {DB_PATH}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(SQL).fetchall()
    finally:
        conn.close()

    foods = []
    for row in rows:
        foods.append(
            [
                row[0],
                str(row[1]),
                row[2],
                row[3],
                row[4],
                row[5],
                row[6],
                row[7],
                row[8],
                row[9],
                row[10],
                row[11],
                row[12],
                row[13],
            ]
        )

    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fields": FIELDS,
        "foods": foods,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    size_mb = OUTPUT_PATH.stat().st_size / (1024 * 1024)
    print(f"Exported {len(foods)} foods to {OUTPUT_PATH} ({size_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
