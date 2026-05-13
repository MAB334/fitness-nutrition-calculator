from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import sqlite3


CATALOG_SELECT = """
WITH food_catalog AS (
    SELECT
        'chinanutri_fq' AS source,
        CAST(food_id AS TEXT) AS source_food_id,
        food_name AS name,
        other_name AS alias_name,
        NULL AS brand,
        category_one_name AS category_top,
        category_two_name AS category_sub,
        'basic_food' AS food_type,
        energy_kcal_100g,
        protein_g_100g,
        fat_g_100g,
        carb_g_100g,
        fiber_g_100g,
        sodium_mg_100g,
        detail_url
    FROM fq_food_list

    UNION ALL

    SELECT
        'chinanutri_nlc' AS source,
        unid AS source_food_id,
        product_name AS name,
        NULL AS alias_name,
        COALESCE(NULLIF(brand, ''), manufacturer) AS brand,
        food_category AS category_top,
        net_content AS category_sub,
        'packaged_food' AS food_type,
        energy_kcal_100g,
        protein_g_100g,
        fat_g_100g,
        carb_g_100g,
        NULL AS fiber_g_100g,
        sodium_mg_100g,
        detail_url
    FROM nlc_products

    UNION ALL

    SELECT
        'fatsecret_cn' AS source,
        detail_url AS source_food_id,
        product_name AS name,
        NULL AS alias_name,
        brand_name AS brand,
        source_query AS category_top,
        serving_description AS category_sub,
        'market_food' AS food_type,
        COALESCE(energy_kcal_100g, energy_kcal) AS energy_kcal_100g,
        COALESCE(protein_g_100g, protein_g) AS protein_g_100g,
        COALESCE(fat_g_100g, fat_g) AS fat_g_100g,
        COALESCE(carb_g_100g, carb_g) AS carb_g_100g,
        NULL AS fiber_g_100g,
        COALESCE(sodium_mg_100g, sodium_mg) AS sodium_mg_100g,
        detail_url
    FROM fatsecret_products
    WHERE COALESCE(archived, 0) = 0
)
"""

SEARCHABLE_PREDICATE = """
energy_kcal_100g IS NOT NULL
AND protein_g_100g IS NOT NULL
AND fat_g_100g IS NOT NULL
AND carb_g_100g IS NOT NULL
"""

COMMON_QUERY_EXPANSIONS = {
    "鸡胸肉": ("鸡胸脯肉", "鸡肉", "鸡柳"),
    "鸡胸": ("鸡胸脯肉", "鸡肉", "鸡柳"),
    "鸡蛋": ("蛋", "鸡蛋"),
    "米饭": ("白米饭", "米饭(蒸)"),
    "燕麦": ("燕麦片",),
    "蛋白粉": ("乳清蛋白", "乳清蛋白粉"),
    "无糖豆浆": ("豆浆",),
    "希腊酸奶": ("酸奶",),
    "全麦面包": ("面包", "吐司"),
    "西红柿炒蛋": ("番茄炒蛋", "番茄鸡蛋", "西红柿鸡蛋"),
    "番茄炒蛋": ("西红柿炒蛋", "西红柿鸡蛋", "番茄鸡蛋"),
    "蛋炒饭": ("炒饭",),
    "宫保鸡丁": ("宫保鸡丁饭",),
    "麻婆豆腐": ("麻婆豆腐饭",),
}

PACKAGED_HINT_RE = re.compile(r"[0-9a-zA-Z]")
PROCESSED_KEYWORDS = (
    "干",
    "肠",
    "丸",
    "卷",
    "串",
    "条",
    "棒",
    "酱",
    "卤",
    "炸",
    "烤",
    "火腿",
    "汉堡",
    "饭团",
    "锅巴",
    "薯片",
    "饼干",
    "饮料",
    "奶茶",
    "味",
)


@dataclass(frozen=True)
class FoodRecord:
    source: str
    source_food_id: str
    name: str
    alias_name: str | None
    brand: str | None
    category_top: str | None
    category_sub: str | None
    food_type: str
    energy_kcal_100g: float | None
    protein_g_100g: float | None
    fat_g_100g: float | None
    carb_g_100g: float | None
    fiber_g_100g: float | None
    sodium_mg_100g: float | None
    detail_url: str | None

    @property
    def display_name(self) -> str:
        if self.brand and self.brand not in self.name:
            return f"{self.brand} {self.name}"
        return self.name

    def to_summary_dict(self) -> dict:
        payload = asdict(self)
        payload["display_name"] = self.display_name
        return payload


def _build_virtual_food_records() -> tuple[FoodRecord, ...]:
    return (
        FoodRecord(
            source="virtual_recipe",
            source_food_id="recipe_tomato_egg",
            name="番茄炒蛋",
            alias_name="西红柿炒蛋 番茄鸡蛋 西红柿鸡蛋",
            brand=None,
            category_top="家常菜",
            category_sub="热菜",
            food_type="dish_recipe",
            energy_kcal_100g=108.0,
            protein_g_100g=6.4,
            fat_g_100g=7.1,
            carb_g_100g=4.3,
            fiber_g_100g=0.8,
            sodium_mg_100g=210.0,
            detail_url=None,
        ),
        FoodRecord(
            source="virtual_recipe",
            source_food_id="recipe_egg_fried_rice",
            name="蛋炒饭",
            alias_name="鸡蛋炒饭 家常蛋炒饭",
            brand=None,
            category_top="主食简餐",
            category_sub="炒饭",
            food_type="dish_recipe",
            energy_kcal_100g=186.0,
            protein_g_100g=5.8,
            fat_g_100g=6.1,
            carb_g_100g=26.8,
            fiber_g_100g=0.7,
            sodium_mg_100g=255.0,
            detail_url=None,
        ),
        FoodRecord(
            source="virtual_recipe",
            source_food_id="recipe_mapo_tofu",
            name="麻婆豆腐",
            alias_name="家常麻婆豆腐",
            brand=None,
            category_top="家常菜",
            category_sub="豆腐菜",
            food_type="dish_recipe",
            energy_kcal_100g=126.0,
            protein_g_100g=7.9,
            fat_g_100g=8.3,
            carb_g_100g=4.9,
            fiber_g_100g=0.9,
            sodium_mg_100g=365.0,
            detail_url=None,
        ),
        FoodRecord(
            source="virtual_recipe",
            source_food_id="recipe_kung_pao_chicken",
            name="宫保鸡丁",
            alias_name="宫保鸡丁饭 家常宫保鸡丁",
            brand=None,
            category_top="家常菜",
            category_sub="鸡肉菜",
            food_type="dish_recipe",
            energy_kcal_100g=164.0,
            protein_g_100g=12.6,
            fat_g_100g=9.2,
            carb_g_100g=7.5,
            fiber_g_100g=0.8,
            sodium_mg_100g=398.0,
            detail_url=None,
        ),
        FoodRecord(
            source="virtual_recipe",
            source_food_id="recipe_green_pepper_pork",
            name="青椒肉丝",
            alias_name="青椒炒肉丝 尖椒肉丝",
            brand=None,
            category_top="家常菜",
            category_sub="肉菜",
            food_type="dish_recipe",
            energy_kcal_100g=143.0,
            protein_g_100g=10.7,
            fat_g_100g=9.1,
            carb_g_100g=4.8,
            fiber_g_100g=1.2,
            sodium_mg_100g=310.0,
            detail_url=None,
        ),
        FoodRecord(
            source="virtual_recipe",
            source_food_id="recipe_yuxiang_shredded_pork",
            name="鱼香肉丝",
            alias_name="家常鱼香肉丝",
            brand=None,
            category_top="家常菜",
            category_sub="肉菜",
            food_type="dish_recipe",
            energy_kcal_100g=152.0,
            protein_g_100g=11.4,
            fat_g_100g=8.9,
            carb_g_100g=6.6,
            fiber_g_100g=1.0,
            sodium_mg_100g=335.0,
            detail_url=None,
        ),
        FoodRecord(
            source="virtual_recipe",
            source_food_id="recipe_hot_sour_potato",
            name="酸辣土豆丝",
            alias_name="家常土豆丝 土豆丝",
            brand=None,
            category_top="家常菜",
            category_sub="素菜",
            food_type="dish_recipe",
            energy_kcal_100g=92.0,
            protein_g_100g=1.9,
            fat_g_100g=3.8,
            carb_g_100g=13.2,
            fiber_g_100g=1.6,
            sodium_mg_100g=225.0,
            detail_url=None,
        ),
        FoodRecord(
            source="virtual_recipe",
            source_food_id="recipe_braised_beef_noodles",
            name="红烧牛肉面",
            alias_name="牛肉面 汤面",
            brand=None,
            category_top="面食",
            category_sub="汤面",
            food_type="dish_recipe",
            energy_kcal_100g=137.0,
            protein_g_100g=6.8,
            fat_g_100g=4.9,
            carb_g_100g=16.5,
            fiber_g_100g=0.9,
            sodium_mg_100g=320.0,
            detail_url=None,
        ),
    )


VIRTUAL_FOOD_RECORDS = _build_virtual_food_records()
VIRTUAL_FOOD_MAP = {(record.source, record.source_food_id): record for record in VIRTUAL_FOOD_RECORDS}


def normalize_search_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def expand_query_terms(query: str) -> list[str]:
    normalized = normalize_search_text(query)
    if not normalized:
        return []
    terms: list[str] = [normalized]
    for key, expansions in COMMON_QUERY_EXPANSIONS.items():
        if normalized == key or key in normalized:
            terms.extend(expansions)
    if normalized.endswith("片") and len(normalized) > 1:
        terms.append(normalized[:-1])
    if normalized.startswith("无糖") and len(normalized) > 2:
        terms.append(normalized[2:])
    unique_terms: list[str] = []
    seen: set[str] = set()
    for term in terms:
        cleaned = normalize_search_text(term)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        unique_terms.append(cleaned)
    return unique_terms


def search_virtual_food_records(query: str, limit: int = 20) -> list[FoodRecord]:
    normalized = normalize_search_text(query)
    if not normalized:
        return []
    expanded_terms = expand_query_terms(normalized)
    matches: list[FoodRecord] = []
    for record in VIRTUAL_FOOD_RECORDS:
        haystacks = [
            normalize_search_text(record.name),
            normalize_search_text(record.alias_name),
            normalize_search_text(record.brand),
            normalize_search_text(record.category_top),
            normalize_search_text(record.category_sub),
        ]
        if any(term and any(term in haystack for haystack in haystacks if haystack) for term in expanded_terms):
            matches.append(record)
    matches.sort(key=lambda item: build_search_sort_key(item, normalized, expanded_terms))
    return matches[:limit]


def has_packaged_query_intent(query: str) -> bool:
    normalized = normalize_search_text(query)
    return bool(PACKAGED_HINT_RE.search(normalized))


def has_processed_query_intent(query: str) -> bool:
    normalized = normalize_search_text(query)
    return any(keyword in normalized for keyword in PROCESSED_KEYWORDS)


def record_has_processed_hint(record: FoodRecord) -> bool:
    haystack = " ".join(filter(None, [record.name, record.alias_name, record.brand, record.category_top, record.category_sub]))
    return any(keyword in haystack for keyword in PROCESSED_KEYWORDS)


def _match_rank(record: FoodRecord, query: str, expanded_terms: list[str]) -> int:
    name = normalize_search_text(record.name)
    alias = normalize_search_text(record.alias_name)
    brand = normalize_search_text(record.brand)
    category = normalize_search_text(record.category_top)

    if name == query:
        return 0
    if alias == query:
        return 1
    if name.startswith(query):
        return 2
    if alias.startswith(query):
        return 3
    if query in name:
        return 4
    if query in alias:
        return 5
    for term in expanded_terms[1:]:
        if name == term:
            return 6
        if name.startswith(term):
            return 7
        if term in name:
            return 8
        if term in alias:
            return 9
    if query and query in brand:
        return 10
    if query and query in category:
        return 11
    return 12


def build_search_sort_key(record: FoodRecord, query: str, expanded_terms: list[str]) -> tuple:
    packaged_intent = has_packaged_query_intent(query)
    processed_query_intent = has_processed_query_intent(query)
    match_rank = _match_rank(record, query, expanded_terms)
    normalized_name = normalize_search_text(record.name)
    normalized_alias = normalize_search_text(record.alias_name)
    expanded_basic_rank = 1
    if not packaged_intent and not processed_query_intent and record.food_type == "basic_food":
        for term in expanded_terms[1:]:
            if normalized_name == term or normalized_alias == term:
                expanded_basic_rank = 0
                break
            if normalized_name.startswith(term) or normalized_alias.startswith(term):
                expanded_basic_rank = 0
                break
    food_type_rank = {
        "basic_food": 0,
        "dish_recipe": 1,
        "packaged_food": 1,
        "market_food": 2,
    }.get(record.food_type, 3)
    if packaged_intent and record.brand and query in normalize_search_text(record.display_name):
        food_type_rank = max(0, food_type_rank - 1)
    processed_rank = 0 if packaged_intent or processed_query_intent else int(record_has_processed_hint(record))
    source_rank = 0 if record.source == "chinanutri_fq" else 1
    name = normalize_search_text(record.display_name)
    name_length_rank = abs(len(name) - len(query)) if query and query in name else len(name)
    protein_rank = -(record.protein_g_100g or 0.0)
    kcal_rank = record.energy_kcal_100g or 0.0
    return (
        expanded_basic_rank,
        match_rank,
        food_type_rank,
        processed_rank,
        source_rank,
        name_length_rank,
        protein_rank,
        kcal_rank,
        record.display_name,
    )


class CatalogRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    @contextmanager
    def connect(self):
        if not self.db_path.exists():
            raise FileNotFoundError(f"Nutrition database not found: {self.db_path}")
        conn = sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def search_foods(self, query: str, limit: int = 20) -> list[FoodRecord]:
        cleaned = " ".join(query.split())
        limit = max(1, min(limit, 50))
        with self.connect() as conn:
            if not cleaned:
                sql = (
                    CATALOG_SELECT
                    + """
                    SELECT *
                    FROM food_catalog
                    WHERE
                        """
                    + SEARCHABLE_PREDICATE
                    + """
                    ORDER BY
                        CASE food_type
                            WHEN 'basic_food' THEN 0
                            WHEN 'packaged_food' THEN 1
                            ELSE 2
                        END,
                        CASE WHEN protein_g_100g IS NULL THEN 1 ELSE 0 END,
                        protein_g_100g DESC,
                        name
                    LIMIT ?
                    """
                )
                rows = conn.execute(sql, (limit,)).fetchall()
            else:
                candidate_limit = max(60, limit * 6)
                rows = self._search_candidates(conn, cleaned, candidate_limit)
        records = [self._row_to_record(row) for row in rows]
        if not cleaned:
            return records
        records.extend(search_virtual_food_records(cleaned, limit=max(6, limit)))
        expanded_terms = expand_query_terms(cleaned)
        normalized_query = normalize_search_text(cleaned)
        records.sort(key=lambda item: build_search_sort_key(item, normalized_query, expanded_terms))
        return records[:limit]

    def get_food(self, source: str, source_food_id: str) -> FoodRecord | None:
        virtual = VIRTUAL_FOOD_MAP.get((source, source_food_id))
        if virtual is not None:
            return virtual
        with self.connect() as conn:
            sql = (
                CATALOG_SELECT
                + """
                SELECT *
                FROM food_catalog
                WHERE source = ? AND source_food_id = ?
                LIMIT 1
                """
            )
            row = conn.execute(sql, (source, source_food_id)).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def _search_candidates(self, conn: sqlite3.Connection, query: str, candidate_limit: int) -> list[sqlite3.Row]:
        seen: set[tuple[str, str]] = set()
        collected: list[sqlite3.Row] = []
        sql = (
            CATALOG_SELECT
            + """
            SELECT *
            FROM food_catalog
            WHERE
                (
                    name LIKE ?
                    OR COALESCE(alias_name, '') LIKE ?
                    OR COALESCE(brand, '') LIKE ?
                    OR COALESCE(category_top, '') LIKE ?
                )
                AND
                """
            + SEARCHABLE_PREDICATE
            + """
            ORDER BY
                CASE
                    WHEN name = ? THEN 0
                    WHEN name LIKE ? THEN 1
                    WHEN COALESCE(alias_name, '') = ? THEN 2
                    WHEN COALESCE(alias_name, '') LIKE ? THEN 3
                    WHEN COALESCE(brand, '') = ? THEN 4
                    ELSE 5
                END,
                CASE food_type
                    WHEN 'basic_food' THEN 0
                    WHEN 'packaged_food' THEN 1
                    ELSE 2
                END,
                CASE WHEN protein_g_100g IS NULL THEN 1 ELSE 0 END,
                protein_g_100g DESC,
                name
            LIMIT ?
            """
        )
        for term in expand_query_terms(query):
            exact = term
            prefix = f"{term}%"
            fuzzy = f"%{term}%"
            params = (fuzzy, fuzzy, fuzzy, fuzzy, exact, prefix, exact, prefix, exact, candidate_limit)
            rows = conn.execute(sql, params).fetchall()
            for row in rows:
                marker = (row["source"], str(row["source_food_id"]))
                if marker in seen:
                    continue
                seen.add(marker)
                collected.append(row)
        return collected

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> FoodRecord:
        return FoodRecord(
            source=row["source"],
            source_food_id=str(row["source_food_id"]),
            name=row["name"],
            alias_name=row["alias_name"],
            brand=row["brand"],
            category_top=row["category_top"],
            category_sub=row["category_sub"],
            food_type=row["food_type"],
            energy_kcal_100g=row["energy_kcal_100g"],
            protein_g_100g=row["protein_g_100g"],
            fat_g_100g=row["fat_g_100g"],
            carb_g_100g=row["carb_g_100g"],
            fiber_g_100g=row["fiber_g_100g"],
            sodium_mg_100g=row["sodium_mg_100g"],
            detail_url=row["detail_url"],
        )
