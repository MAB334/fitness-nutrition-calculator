from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import random
import re
import sqlite3
import threading
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup


THREAD_LOCAL = threading.local()


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "china_sources.json"
DATA_ROOT = Path(os.environ.get("CHINA_NUTRITION_DATA_ROOT", r"E:\爬虫抓包数据\china"))
RAW_DIR = DATA_ROOT / "raw"
PROCESSED_DIR = DATA_ROOT / "processed"
DEFAULT_DB_PATH = PROCESSED_DIR / "china_nutrition.db"
DEFAULT_STATS_PATH = PROCESSED_DIR / "china_stats.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 45
REQUEST_PAUSE_SECONDS = 0.15
FATSECRET_REQUEST_PAUSE_SECONDS = 0.35
FATSECRET_MAX_RETRIES = 6
FATSECRET_NO_GROWTH_PAGE_LIMIT = 8
FQ_HOME_URL = "https://nlc.chinanutri.cn/fq/"
FQ_LIST_API = "https://nlc.chinanutri.cn/fq/FoodInfoQueryAction!queryFoodInfoList.do"
FQ_DETAIL_URL_TEMPLATE = "https://nlc.chinanutri.cn/fq/foodinfo/{id}.html"
NLC_LIST_URL_TEMPLATE = "https://nlc.chinanutri.cn/foodlist__{page}.htm"
NLC_DETAIL_URL_TEMPLATE = "https://nlc.chinanutri.cn/food/{id}.html"
FATSECRET_BRANDS_URL_TEMPLATE = "https://www.fatsecret.cn/Default.aspx?pa=brands&f={letter}&t={brand_type}"
FATSECRET_BRANDS_PAGE_URL_TEMPLATE = "https://www.fatsecret.cn/Default.aspx?pa=brands&pg={page_index}&f={letter}&t={brand_type}"
FATSECRET_SEARCH_URL_TEMPLATE = "https://www.fatsecret.cn/%E7%83%AD%E9%87%8F%E8%90%A5%E5%85%BB/search?q={query}"
FATSECRET_DETAIL_BASE = "https://www.fatsecret.cn"
FATSECRET_PRIORITY_PATTERN = re.compile(r"(蛋白粉|乳清|增肌|代餐|燕麦|麦片|米糊|米粉)", re.IGNORECASE)
FATSECRET_FOOD_TERMS = [
    "蛋白粉", "乳清", "增肌粉", "代餐", "燕麦", "麦片", "米糊", "米粉", "牛奶", "酸奶",
    "面包", "咖啡", "豆浆", "鸡胸", "鸡蛋", "能量棒", "奶昔", "饼干", "巧克力", "饮料",
    "坚果", "豆腐", "豆奶", "奶酪", "吐司", "麦麸", "酸乳", "果汁", "汽水", "可可",
]

FQ_SUMMARY_FIELDS = [
    ("food_name", "食物名称"),
    ("other_name", "别名或俗名"),
    ("english_name", "英文名称"),
    ("edible_portion", "食部"),
    ("water", "水分"),
    ("energy_kj", "能量"),
    ("protein", "蛋白质"),
    ("fat", "脂肪"),
    ("cholesterol", "胆固醇"),
    ("ash", "灰分"),
    ("carbohydrate", "碳水化合物"),
    ("dietary_fiber", "总膳食纤维"),
    ("carotene", "胡萝卜素"),
    ("vitamin_a", "维生素A"),
    ("alpha_te", "α-TE"),
    ("thiamin", "硫胺素"),
    ("riboflavin", "核黄素"),
    ("niacin", "烟酸"),
    ("vitamin_c", "维生素C"),
    ("calcium", "钙"),
    ("phosphorus", "磷"),
    ("potassium", "钾"),
    ("sodium", "钠"),
    ("magnesium", "镁"),
    ("iron", "铁"),
    ("zinc", "锌"),
    ("selenium", "硒"),
    ("copper", "铜"),
    ("manganese", "锰"),
    ("iodine", "碘"),
    ("sfa_percent", "饱和脂肪酸"),
    ("mufa_percent", "单不饱和脂肪酸"),
    ("pufa_percent", "多不饱和脂肪酸"),
    ("fatty_acid_total_percent", "合计")
]

FQ_CANONICAL_AMOUNT_KEYS = {
    "water": ("water_g_100g", "water_g_100g_raw"),
    "energy_kj": ("energy_kj_100g", "energy_kj_100g_raw"),
    "protein": ("protein_g_100g", "protein_g_100g_raw"),
    "fat": ("fat_g_100g", "fat_g_100g_raw"),
    "cholesterol": ("cholesterol_mg_100g", "cholesterol_mg_100g_raw"),
    "ash": ("ash_g_100g", "ash_g_100g_raw"),
    "carbohydrate": ("carb_g_100g", "carb_g_100g_raw"),
    "dietary_fiber": ("fiber_g_100g", "fiber_g_100g_raw"),
    "carotene": ("carotene_ug_100g", "carotene_ug_100g_raw"),
    "vitamin_a": ("vitamin_a_ug_100g", "vitamin_a_ug_100g_raw"),
    "thiamin": ("thiamin_mg_100g", "thiamin_mg_100g_raw"),
    "riboflavin": ("riboflavin_mg_100g", "riboflavin_mg_100g_raw"),
    "niacin": ("niacin_mg_100g", "niacin_mg_100g_raw"),
    "vitamin_c": ("vitamin_c_mg_100g", "vitamin_c_mg_100g_raw"),
    "calcium": ("calcium_mg_100g", "calcium_mg_100g_raw"),
    "phosphorus": ("phosphorus_mg_100g", "phosphorus_mg_100g_raw"),
    "potassium": ("potassium_mg_100g", "potassium_mg_100g_raw"),
    "sodium": ("sodium_mg_100g", "sodium_mg_100g_raw"),
    "magnesium": ("magnesium_mg_100g", "magnesium_mg_100g_raw"),
    "iron": ("iron_mg_100g", "iron_mg_100g_raw"),
    "zinc": ("zinc_mg_100g", "zinc_mg_100g_raw"),
    "selenium": ("selenium_ug_100g", "selenium_ug_100g_raw"),
    "copper": ("copper_mg_100g", "copper_mg_100g_raw"),
    "manganese": ("manganese_mg_100g", "manganese_mg_100g_raw"),
    "iodine": ("iodine_ug_100g", "iodine_ug_100g_raw"),
    "sfa_percent": ("sfa_percent", "sfa_percent_raw"),
    "mufa_percent": ("mufa_percent", "mufa_percent_raw"),
    "pufa_percent": ("pufa_percent", "pufa_percent_raw"),
    "fatty_acid_total_percent": ("fatty_acid_total_percent", "fatty_acid_total_percent_raw")
}

NLC_NUTRIENT_KEYS = {
    "能量": ("energy_kj_100g", "energy_kj_100g_raw"),
    "蛋白质": ("protein_g_100g", "protein_g_100g_raw"),
    "脂肪": ("fat_g_100g", "fat_g_100g_raw"),
    "碳水化合物": ("carb_g_100g", "carb_g_100g_raw"),
    "钠": ("sodium_mg_100g", "sodium_mg_100g_raw")
}


@dataclass
class AmountValue:
    raw: str | None
    numeric: float | None
    unit: str | None


@dataclass
class ServingInfo:
    raw: str | None
    amount_numeric: float | None
    amount_unit: str | None
    normalized_basis: str | None


def ensure_directories() -> None:
    (RAW_DIR / "chinanutri_fq" / "pages").mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "chinanutri_fq" / "details").mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "chinanutri_nlc" / "pages").mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "chinanutri_nlc" / "details").mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "fatsecret_cn" / "brands").mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "fatsecret_cn" / "search").mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "fatsecret_cn" / "details").mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def load_sources() -> dict[str, dict]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {item["key"]: item for item in payload["sources"]}


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    )
    return session


def get_thread_session() -> requests.Session:
    session = getattr(THREAD_LOCAL, "session", None)
    if session is None:
        session = build_session()
        THREAD_LOCAL.session = session
    return session


def pause() -> None:
    time.sleep(REQUEST_PAUSE_SECONDS)


def fetch_text(session: requests.Session, url: str, *, referer: str | None = None, method: str = "GET", data: dict | None = None) -> str:
    headers = {}
    if referer:
        headers["Referer"] = referer
    response = session.request(method, url, data=data, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    if response.encoding is None:
        response.encoding = response.apparent_encoding or "utf-8"
    pause()
    return response.text


def fetch_json(session: requests.Session, url: str, *, referer: str | None = None, data: dict | None = None) -> dict:
    text = fetch_text(session, url, referer=referer, method="POST", data=data)
    return json.loads(text)


def fetch_text_retrying(
    session: requests.Session,
    url: str,
    *,
    referer: str | None = None,
    pause_seconds: float = FATSECRET_REQUEST_PAUSE_SECONDS,
    max_retries: int = FATSECRET_MAX_RETRIES,
) -> str:
    headers = {}
    if referer:
        headers["Referer"] = referer
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code in {429, 500, 502, 503, 504}:
            last_error = requests.HTTPError(f"fatsecret temporary status {response.status_code} for {url}")
            wait_seconds = min(12.0, pause_seconds * (2 ** attempt) + random.uniform(0.1, 0.5))
            print(f"[fatsecret] retry {attempt}/{max_retries} status {response.status_code}: {url}")
            pause_for(wait_seconds)
            continue
        response.raise_for_status()
        if response.encoding is None or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        pause_for(pause_seconds + random.uniform(0.0, 0.15))
        return response.text
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"failed to fetch {url}")


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def create_connection(db_path: Path) -> sqlite3.Connection:
    ensure_directories()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS source_registry (
            source_key TEXT PRIMARY KEY,
            source_name TEXT NOT NULL,
            provider TEXT NOT NULL,
            home_url TEXT NOT NULL,
            license_note TEXT,
            last_crawled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS fq_categories (
            category_one_id INTEGER NOT NULL,
            category_one_name TEXT NOT NULL,
            category_two_id INTEGER NOT NULL,
            category_two_name TEXT NOT NULL,
            list_url TEXT NOT NULL,
            PRIMARY KEY (category_one_id, category_two_id)
        );

        CREATE TABLE IF NOT EXISTS fq_food_list (
            food_id INTEGER PRIMARY KEY,
            food_name TEXT,
            other_name TEXT,
            english_name TEXT,
            category_one_id INTEGER,
            category_one_name TEXT,
            category_two_id INTEGER,
            category_two_name TEXT,
            list_page INTEGER,
            detail_url TEXT,
            image_path TEXT,
            edible_portion_raw TEXT,
            edible_portion_numeric REAL,
            edible_portion_unit TEXT,
            water_g_100g_raw TEXT,
            water_g_100g REAL,
            energy_kj_100g_raw TEXT,
            energy_kj_100g REAL,
            energy_kcal_100g REAL,
            protein_g_100g_raw TEXT,
            protein_g_100g REAL,
            fat_g_100g_raw TEXT,
            fat_g_100g REAL,
            cholesterol_mg_100g_raw TEXT,
            cholesterol_mg_100g REAL,
            ash_g_100g_raw TEXT,
            ash_g_100g REAL,
            carb_g_100g_raw TEXT,
            carb_g_100g REAL,
            fiber_g_100g_raw TEXT,
            fiber_g_100g REAL,
            carotene_ug_100g_raw TEXT,
            carotene_ug_100g REAL,
            vitamin_a_ug_100g_raw TEXT,
            vitamin_a_ug_100g REAL,
            alpha_te_raw TEXT,
            thiamin_mg_100g_raw TEXT,
            thiamin_mg_100g REAL,
            riboflavin_mg_100g_raw TEXT,
            riboflavin_mg_100g REAL,
            niacin_mg_100g_raw TEXT,
            niacin_mg_100g REAL,
            vitamin_c_mg_100g_raw TEXT,
            vitamin_c_mg_100g REAL,
            calcium_mg_100g_raw TEXT,
            calcium_mg_100g REAL,
            phosphorus_mg_100g_raw TEXT,
            phosphorus_mg_100g REAL,
            potassium_mg_100g_raw TEXT,
            potassium_mg_100g REAL,
            sodium_mg_100g_raw TEXT,
            sodium_mg_100g REAL,
            magnesium_mg_100g_raw TEXT,
            magnesium_mg_100g REAL,
            iron_mg_100g_raw TEXT,
            iron_mg_100g REAL,
            zinc_mg_100g_raw TEXT,
            zinc_mg_100g REAL,
            selenium_ug_100g_raw TEXT,
            selenium_ug_100g REAL,
            copper_mg_100g_raw TEXT,
            copper_mg_100g REAL,
            manganese_mg_100g_raw TEXT,
            manganese_mg_100g REAL,
            iodine_ug_100g_raw TEXT,
            iodine_ug_100g REAL,
            sfa_percent_raw TEXT,
            sfa_percent REAL,
            mufa_percent_raw TEXT,
            mufa_percent REAL,
            pufa_percent_raw TEXT,
            pufa_percent REAL,
            fatty_acid_total_percent_raw TEXT,
            fatty_acid_total_percent REAL,
            raw_list_row_json TEXT,
            crawled_at TEXT,
            detail_crawled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS fq_food_details (
            food_id INTEGER PRIMARY KEY,
            food_name TEXT,
            category_one_name TEXT,
            category_two_name TEXT,
            image_url TEXT,
            raw_html_path TEXT,
            statement TEXT,
            crawled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS fq_food_nutrients (
            food_id INTEGER NOT NULL,
            row_order INTEGER NOT NULL,
            nutrient_group TEXT,
            nutrient_name TEXT,
            amount_raw TEXT,
            amount_numeric REAL,
            amount_unit TEXT,
            peer_rank TEXT,
            peer_average_raw TEXT,
            peer_average_numeric REAL,
            peer_average_unit TEXT,
            level_text TEXT,
            PRIMARY KEY (food_id, row_order)
        );

        CREATE TABLE IF NOT EXISTS nlc_products (
            unid TEXT PRIMARY KEY,
            product_name TEXT,
            manufacturer TEXT,
            brand TEXT,
            food_category TEXT,
            ingredients TEXT,
            net_content TEXT,
            barcode TEXT,
            storage_method TEXT,
            origin TEXT,
            image_url TEXT,
            detail_url TEXT,
            raw_html_path TEXT,
            source_list_page INTEGER,
            energy_kj_100g_raw TEXT,
            energy_kj_100g REAL,
            energy_kcal_100g REAL,
            protein_g_100g_raw TEXT,
            protein_g_100g REAL,
            fat_g_100g_raw TEXT,
            fat_g_100g REAL,
            carb_g_100g_raw TEXT,
            carb_g_100g REAL,
            sodium_mg_100g_raw TEXT,
            sodium_mg_100g REAL,
            energy_nrv_pct TEXT,
            protein_nrv_pct TEXT,
            fat_nrv_pct TEXT,
            carb_nrv_pct TEXT,
            sodium_nrv_pct TEXT,
            energy_rank TEXT,
            protein_rank TEXT,
            fat_rank TEXT,
            carb_rank TEXT,
            sodium_rank TEXT,
            crawled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS nlc_product_nutrients (
            unid TEXT NOT NULL,
            row_order INTEGER NOT NULL,
            nutrient_name TEXT,
            amount_raw TEXT,
            amount_numeric REAL,
            amount_unit TEXT,
            nrv_pct TEXT,
            peer_rank TEXT,
            PRIMARY KEY (unid, row_order)
        );

        CREATE TABLE IF NOT EXISTS fatsecret_brands (
            brand_slug TEXT PRIMARY KEY,
            brand_name TEXT NOT NULL,
            brand_url TEXT NOT NULL,
            archive_url TEXT,
            brand_type INTEGER NOT NULL,
            brand_type_label TEXT NOT NULL,
            directory_letter TEXT NOT NULL,
            directory_page INTEGER NOT NULL,
            search_total_results INTEGER,
            search_pages_crawled INTEGER,
            search_completed_at TEXT,
            crawled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS fatsecret_products (
            detail_url TEXT PRIMARY KEY,
            brand_slug TEXT,
            brand_name TEXT,
            product_name TEXT,
            source_query TEXT,
            source_page INTEGER,
            source_rank INTEGER,
            archived INTEGER DEFAULT 0,
            search_summary_text TEXT,
            serving_description TEXT,
            serving_amount_numeric REAL,
            serving_amount_unit TEXT,
            normalized_basis TEXT,
            energy_kj_raw TEXT,
            energy_kj REAL,
            energy_kcal REAL,
            protein_g REAL,
            fat_g REAL,
            saturated_fat_g REAL,
            carb_g REAL,
            sugar_g REAL,
            sodium_mg REAL,
            energy_kj_100g REAL,
            energy_kcal_100g REAL,
            protein_g_100g REAL,
            fat_g_100g REAL,
            saturated_fat_g_100g REAL,
            carb_g_100g REAL,
            sugar_g_100g REAL,
            sodium_mg_100g REAL,
            last_updated_at TEXT,
            detail_source TEXT,
            raw_detail_html_path TEXT,
            discovered_at TEXT,
            detail_crawled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS fatsecret_search_terms (
            term TEXT PRIMARY KEY,
            source_kind TEXT NOT NULL,
            total_results INTEGER,
            pages_crawled INTEGER,
            completed_at TEXT,
            crawled_at TEXT
        );
        """
    )
    conn.commit()


def register_source(conn: sqlite3.Connection, source: dict) -> None:
    conn.execute(
        """
        INSERT INTO source_registry (source_key, source_name, provider, home_url, license_note, last_crawled_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(source_key) DO UPDATE SET
            source_name = excluded.source_name,
            provider = excluded.provider,
            home_url = excluded.home_url,
            license_note = excluded.license_note,
            last_crawled_at = excluded.last_crawled_at
        """,
        (
            source["key"],
            source["name"],
            source["provider"],
            source["home_url"],
            source["license_note"],
        ),
    )
    conn.commit()


def parse_amount(value: str | None) -> AmountValue:
    if value is None:
        return AmountValue(None, None, None)
    cleaned = value.replace("\xa0", " ").strip()
    if cleaned == "":
        return AmountValue(value, None, None)
    if cleaned == "—":
        return AmountValue(value, None, None)
    if cleaned == "Tr":
        return AmountValue(value, 0.0, "Tr")
    match = re.match(r"^\s*([-+]?\d+(?:\.\d+)?)\s*([%A-Za-zμkJgmgUGu]+)?\s*$", cleaned)
    if not match:
        return AmountValue(value, None, None)
    number = float(match.group(1))
    unit = match.group(2) or None
    return AmountValue(value, number, unit)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", "", value).strip().casefold()


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "_", value.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "item"


def parse_serving_info(serving_text: str | None) -> ServingInfo:
    if not serving_text:
        return ServingInfo(None, None, None, None)
    cleaned = " ".join(serving_text.replace("\xa0", " ").split())
    amount_match = re.search(r"\(([\d.]+)\s*(克|毫升|g|ml)\)", cleaned, re.IGNORECASE)
    if amount_match:
        amount_numeric = float(amount_match.group(1))
        amount_unit = amount_match.group(2).lower()
    else:
        direct_match = re.fullmatch(r"([\d.]+)\s*(克|毫升|g|ml)", cleaned, re.IGNORECASE)
        if direct_match:
            amount_numeric = float(direct_match.group(1))
            amount_unit = direct_match.group(2).lower()
        else:
            amount_numeric = None
            amount_unit = None
    normalized_basis = None
    if amount_numeric and amount_numeric > 0 and amount_unit:
        normalized_basis = f"100{amount_unit}"
    return ServingInfo(cleaned, amount_numeric, amount_unit, normalized_basis)


def normalize_per_100(value: float | None, serving: ServingInfo) -> float | None:
    if value is None or serving.amount_numeric is None or serving.amount_numeric <= 0:
        return None
    if serving.amount_unit not in {"克", "g", "毫升", "ml"}:
        return None
    return round(value / serving.amount_numeric * 100, 4)


def pause_for(seconds: float) -> None:
    time.sleep(seconds)


def to_kcal_from_kj(kj: float | None) -> float | None:
    if kj is None:
        return None
    return round(kj / 4.184, 2)


def save_fq_category(conn: sqlite3.Connection, category: dict) -> None:
    conn.execute(
        """
        INSERT INTO fq_categories (
            category_one_id, category_one_name, category_two_id, category_two_name, list_url
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(category_one_id, category_two_id) DO UPDATE SET
            category_one_name = excluded.category_one_name,
            category_two_name = excluded.category_two_name,
            list_url = excluded.list_url
        """,
        (
            category["category_one_id"],
            category["category_one_name"],
            category["category_two_id"],
            category["category_two_name"],
            category["list_url"],
        ),
    )


def discover_fq_categories(session: requests.Session) -> list[dict]:
    html = fetch_text(session, FQ_HOME_URL)
    save_text(RAW_DIR / "chinanutri_fq" / "home.html", html)
    soup = BeautifulSoup(html, "lxml")
    categories: list[dict] = []
    for box in soup.select("div.food_box"):
        top_link = box.select_one("h3 a")
        if top_link is None:
            continue
        top_href = top_link.get("href", "")
        top_match = re.search(r"foodlist_0_(\d+)_0_0_0_1\.htm", top_href)
        if not top_match:
            continue
        category_one_id = int(top_match.group(1))
        category_one_name = top_link.get_text(strip=True)
        for link in box.select("ul.food_list a"):
            href = link.get("href", "")
            match = re.search(r"foodlist_0_(\d+)_(\d+)_0_0_1\.htm", href)
            if not match:
                continue
            categories.append(
                {
                    "category_one_id": int(match.group(1)),
                    "category_one_name": category_one_name,
                    "category_two_id": int(match.group(2)),
                    "category_two_name": link.get_text(strip=True),
                    "list_url": urljoin(FQ_HOME_URL, href),
                }
            )
    return categories


def upsert_fq_food_list(conn: sqlite3.Connection, payload: dict) -> None:
    columns = sorted(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    update_clause = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "food_id")
    conn.execute(
        f"""
        INSERT INTO fq_food_list ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(food_id) DO UPDATE SET
            {update_clause}
        """,
        tuple(payload[column] for column in columns),
    )


def upsert_fq_food_detail(conn: sqlite3.Connection, payload: dict) -> None:
    columns = sorted(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    update_clause = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "food_id")
    conn.execute(
        f"""
        INSERT INTO fq_food_details ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(food_id) DO UPDATE SET
            {update_clause}
        """,
        tuple(payload[column] for column in columns),
    )


def replace_fq_food_nutrients(conn: sqlite3.Connection, food_id: int, nutrients: list[dict]) -> None:
    conn.execute("DELETE FROM fq_food_nutrients WHERE food_id = ?", (food_id,))
    for row in nutrients:
        conn.execute(
            """
            INSERT INTO fq_food_nutrients (
                food_id, row_order, nutrient_group, nutrient_name, amount_raw,
                amount_numeric, amount_unit, peer_rank, peer_average_raw,
                peer_average_numeric, peer_average_unit, level_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                food_id,
                row["row_order"],
                row["nutrient_group"],
                row["nutrient_name"],
                row["amount_raw"],
                row["amount_numeric"],
                row["amount_unit"],
                row["peer_rank"],
                row["peer_average_raw"],
                row["peer_average_numeric"],
                row["peer_average_unit"],
                row["level_text"],
            ),
        )


def upsert_nlc_product(conn: sqlite3.Connection, payload: dict) -> None:
    columns = sorted(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    update_clause = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "unid")
    conn.execute(
        f"""
        INSERT INTO nlc_products ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(unid) DO UPDATE SET
            {update_clause}
        """,
        tuple(payload[column] for column in columns),
    )


def replace_nlc_product_nutrients(conn: sqlite3.Connection, unid: str, nutrients: list[dict]) -> None:
    conn.execute("DELETE FROM nlc_product_nutrients WHERE unid = ?", (unid,))
    for row in nutrients:
        conn.execute(
            """
            INSERT INTO nlc_product_nutrients (
                unid, row_order, nutrient_name, amount_raw, amount_numeric, amount_unit, nrv_pct, peer_rank
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                unid,
                row["row_order"],
                row["nutrient_name"],
                row["amount_raw"],
                row["amount_numeric"],
                row["amount_unit"],
                row["nrv_pct"],
                row["peer_rank"],
            ),
        )


def upsert_fatsecret_brand(conn: sqlite3.Connection, payload: dict) -> None:
    columns = sorted(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    update_clause = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "brand_slug")
    conn.execute(
        f"""
        INSERT INTO fatsecret_brands ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(brand_slug) DO UPDATE SET
            {update_clause}
        """,
        tuple(payload[column] for column in columns),
    )


def upsert_fatsecret_product(conn: sqlite3.Connection, payload: dict) -> None:
    columns = sorted(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    update_clause = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "detail_url")
    conn.execute(
        f"""
        INSERT INTO fatsecret_products ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(detail_url) DO UPDATE SET
            {update_clause}
        """,
        tuple(payload[column] for column in columns),
    )


def upsert_fatsecret_search_term(conn: sqlite3.Connection, payload: dict) -> None:
    columns = sorted(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    update_clause = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "term")
    conn.execute(
        f"""
        INSERT INTO fatsecret_search_terms ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(term) DO UPDATE SET
            {update_clause}
        """,
        tuple(payload[column] for column in columns),
    )


def parse_fq_row(row: list, category: dict, page_num: int) -> dict:
    payload: dict[str, object] = {
        "food_id": int(row[0]),
        "food_name": row[2] if len(row) > 2 else None,
        "category_one_id": category["category_one_id"],
        "category_one_name": category["category_one_name"],
        "category_two_id": category["category_two_id"],
        "category_two_name": category["category_two_name"],
        "list_page": page_num,
        "detail_url": FQ_DETAIL_URL_TEMPLATE.format(id=row[0]),
        "image_path": row[1] or None,
        "raw_list_row_json": json.dumps(row, ensure_ascii=False),
        "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    values = list(row[2:])
    for index, (field_key, _field_label) in enumerate(FQ_SUMMARY_FIELDS):
        raw_value = values[index] if index < len(values) else None
        if field_key in {"food_name", "other_name", "english_name"}:
            payload[field_key] = raw_value
            continue
        if field_key == "alpha_te":
            payload["alpha_te_raw"] = raw_value
            continue
        if field_key == "edible_portion":
            amount = parse_amount(raw_value)
            payload["edible_portion_raw"] = amount.raw
            payload["edible_portion_numeric"] = amount.numeric
            payload["edible_portion_unit"] = amount.unit
            continue
        amount = parse_amount(raw_value)
        numeric_key, raw_key = FQ_CANONICAL_AMOUNT_KEYS[field_key]
        payload[raw_key] = amount.raw
        payload[numeric_key] = amount.numeric
        if numeric_key == "energy_kj_100g":
            payload["energy_kcal_100g"] = to_kcal_from_kj(amount.numeric)
    return payload


def parse_fq_detail_html(html: str, food_id: int) -> tuple[dict, list[dict]]:
    soup = BeautifulSoup(html, "lxml")
    breadcrumb_links = soup.select("ol.breadcrumb li a")
    category_one_name = breadcrumb_links[2].get_text(strip=True) if len(breadcrumb_links) >= 3 else None
    category_two_name = breadcrumb_links[3].get_text(strip=True) if len(breadcrumb_links) >= 4 else None
    title = soup.select_one("div.food_introduce h1").get_text(strip=True)
    image = soup.select_one("#bigImg")
    statement = soup.select_one("div.statement p")
    detail_payload = {
        "food_id": food_id,
        "food_name": title,
        "category_one_name": category_one_name,
        "category_two_name": category_two_name,
        "image_url": urljoin(FQ_HOME_URL, image.get("src")) if image else None,
        "statement": statement.get_text(" ", strip=True) if statement else None,
        "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    nutrients: list[dict] = []
    current_group: str | None = None
    rows = soup.select("div.nutrition_table_content table tr")[1:]
    row_order = 0
    for tr in rows:
        cells = tr.find_all("td")
        if not cells:
            continue
        texts = [cell.get_text(" ", strip=True) for cell in cells]
        if len(texts) == 6:
            current_group = texts[0]
            nutrient_name = texts[1]
            amount_raw = texts[2]
            peer_rank = texts[3]
            peer_average_raw = texts[4]
            level_text = cells[5].get_text(" ", strip=True)
        elif len(texts) == 5:
            nutrient_name = texts[0]
            amount_raw = texts[1]
            peer_rank = texts[2]
            peer_average_raw = texts[3]
            level_text = cells[4].get_text(" ", strip=True)
        else:
            continue
        amount = parse_amount(amount_raw)
        peer_average = parse_amount(peer_average_raw)
        nutrients.append(
            {
                "row_order": row_order,
                "nutrient_group": current_group,
                "nutrient_name": nutrient_name,
                "amount_raw": amount.raw,
                "amount_numeric": amount.numeric,
                "amount_unit": amount.unit,
                "peer_rank": peer_rank or None,
                "peer_average_raw": peer_average.raw,
                "peer_average_numeric": peer_average.numeric,
                "peer_average_unit": peer_average.unit,
                "level_text": level_text or None,
            }
        )
        row_order += 1
    return detail_payload, nutrients


def crawl_fq(args: argparse.Namespace) -> None:
    ensure_directories()
    source = load_sources()["chinanutri_fq"]
    session = build_session()
    conn = create_connection(args.db_path)
    init_schema(conn)
    register_source(conn, source)

    try:
        categories = discover_fq_categories(session)
        if args.max_categories:
            categories = categories[: args.max_categories]
        save_json(RAW_DIR / "chinanutri_fq" / "categories.json", categories)
        for category in categories:
            save_fq_category(conn, category)
        conn.commit()

        for category in categories:
            print(f"[fq] category {category['category_one_name']} / {category['category_two_name']}")
            first_page = fetch_json(
                session,
                FQ_LIST_API,
                referer=category["list_url"],
                data={
                    "categoryOne": category["category_one_id"],
                    "categoryTwo": category["category_two_id"],
                    "foodName": "0",
                    "pageNum": 1,
                    "field": "0",
                    "flag": "0",
                },
            )
            total_pages = int(first_page.get("totalPages") or 0)
            if args.max_pages_per_category:
                total_pages = min(total_pages, args.max_pages_per_category)
            for page_num in range(1, total_pages + 1):
                if page_num == 1:
                    payload = first_page
                else:
                    payload = fetch_json(
                        session,
                        FQ_LIST_API,
                        referer=category["list_url"],
                        data={
                            "categoryOne": category["category_one_id"],
                            "categoryTwo": category["category_two_id"],
                            "foodName": "0",
                            "pageNum": page_num,
                            "field": "0",
                            "flag": "0",
                        },
                    )
                save_json(
                    RAW_DIR / "chinanutri_fq" / "pages" / f"cat1_{category['category_one_id']}_cat2_{category['category_two_id']}_page_{page_num}.json",
                    payload,
                )
                rows = payload.get("list") or []
                print(f"[fq] page {page_num}/{total_pages}: {len(rows)} foods")
                for row in rows:
                    list_payload = parse_fq_row(row, category, page_num)
                    upsert_fq_food_list(conn, list_payload)
                conn.commit()

        if not args.skip_details:
            food_rows = conn.execute(
                """
                SELECT food_id, detail_url
                FROM fq_food_list
                WHERE detail_crawled_at IS NULL
                ORDER BY food_id
                """
            ).fetchall()
            if args.max_details:
                food_rows = food_rows[: args.max_details]
            for index, (food_id, detail_url) in enumerate(food_rows, start=1):
                print(f"[fq] detail {index}/{len(food_rows)}: {food_id}")
                html = fetch_text(session, detail_url, referer=FQ_HOME_URL)
                raw_path = RAW_DIR / "chinanutri_fq" / "details" / f"{food_id}.html"
                save_text(raw_path, html)
                detail_payload, nutrients = parse_fq_detail_html(html, int(food_id))
                detail_payload["raw_html_path"] = str(raw_path)
                upsert_fq_food_detail(conn, detail_payload)
                replace_fq_food_nutrients(conn, int(food_id), nutrients)
                conn.execute(
                    "UPDATE fq_food_list SET detail_crawled_at = datetime('now') WHERE food_id = ?",
                    (food_id,),
                )
                conn.commit()

        build_unified_catalog(conn)
        stats = write_stats(conn, args.stats_path)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    finally:
        conn.close()


def parse_nlc_list_page(html: str) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []
    for card in soup.select("div.productbox_list div.product"):
        detail_link = card.select_one("a[href^='food/']")
        if detail_link is None:
            continue
        href = detail_link.get("href", "").strip()
        match = re.search(r"food/([^./]+)\.html", href)
        if not match:
            continue
        unid = match.group(1)
        image = detail_link.find("img")
        name_link = card.select_one("span a")
        items.append(
            {
                "unid": unid,
                "detail_url": urljoin("https://nlc.chinanutri.cn/", href),
                "image_url": urljoin("https://nlc.chinanutri.cn/", image.get("src")) if image else None,
                "product_name": name_link.get_text(" ", strip=True) if name_link else None,
            }
        )
    has_next = False
    for link in soup.select("div.pages a"):
        if link.get_text(strip=True) == "下一页" and link.get("href") not in {"#none", "", None}:
            has_next = True
            break
    return items, has_next


def parse_nlc_detail_html(html: str, unid: str) -> tuple[dict, list[dict]]:
    soup = BeautifulSoup(html, "lxml")
    title = soup.select_one("div.product_introduce h1").get_text(strip=True)
    info_map: dict[str, str] = {}
    info_p = soup.select_one("div.product_introduce p")
    if info_p:
        for text in info_p.stripped_strings:
            cleaned = text.replace("\xa0", " ").strip()
            if "：" in cleaned:
                key, value = cleaned.split("：", 1)
                info_map[key.strip()] = value.strip()
    image = soup.select_one("#preview img")

    product_payload: dict[str, object] = {
        "unid": unid,
        "product_name": title,
        "manufacturer": info_map.get("生产厂家"),
        "brand": info_map.get("品牌"),
        "food_category": info_map.get("食物类别"),
        "ingredients": info_map.get("配料"),
        "net_content": info_map.get("净含量"),
        "barcode": info_map.get("条形码/识别码"),
        "storage_method": info_map.get("储存方法"),
        "origin": info_map.get("产地"),
        "image_url": urljoin("https://nlc.chinanutri.cn/", image.get("src")) if image else None,
        "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    nutrients: list[dict] = []
    rows = soup.select("div.nutrition_left table tr")[1:]
    nrv_by_key: dict[str, str | None] = {}
    rank_by_key: dict[str, str | None] = {}
    for row_order, tr in enumerate(rows):
        cells = [cell.get_text(" ", strip=True) for cell in tr.find_all("td")]
        if len(cells) < 4:
            continue
        nutrient_name, amount_raw, nrv_pct, peer_rank = cells[:4]
        amount = parse_amount(amount_raw)
        nutrients.append(
            {
                "row_order": row_order,
                "nutrient_name": nutrient_name,
                "amount_raw": amount.raw,
                "amount_numeric": amount.numeric,
                "amount_unit": amount.unit,
                "nrv_pct": nrv_pct,
                "peer_rank": peer_rank,
            }
        )
        if nutrient_name in NLC_NUTRIENT_KEYS:
            numeric_key, raw_key = NLC_NUTRIENT_KEYS[nutrient_name]
            product_payload[raw_key] = amount.raw
            product_payload[numeric_key] = amount.numeric
            nrv_by_key[nutrient_name] = nrv_pct
            rank_by_key[nutrient_name] = peer_rank

    if product_payload.get("energy_kj_100g") is not None:
        product_payload["energy_kcal_100g"] = to_kcal_from_kj(float(product_payload["energy_kj_100g"]))

    product_payload["energy_nrv_pct"] = nrv_by_key.get("能量")
    product_payload["protein_nrv_pct"] = nrv_by_key.get("蛋白质")
    product_payload["fat_nrv_pct"] = nrv_by_key.get("脂肪")
    product_payload["carb_nrv_pct"] = nrv_by_key.get("碳水化合物")
    product_payload["sodium_nrv_pct"] = nrv_by_key.get("钠")
    product_payload["energy_rank"] = rank_by_key.get("能量")
    product_payload["protein_rank"] = rank_by_key.get("蛋白质")
    product_payload["fat_rank"] = rank_by_key.get("脂肪")
    product_payload["carb_rank"] = rank_by_key.get("碳水化合物")
    product_payload["sodium_rank"] = rank_by_key.get("钠")
    return product_payload, nutrients


def fetch_nlc_detail_bundle(item: dict, list_url: str, page: int) -> tuple[dict, list[dict]]:
    session = get_thread_session()
    detail_html = fetch_text(session, item["detail_url"], referer=list_url)
    detail_raw_path = RAW_DIR / "chinanutri_nlc" / "details" / f"{item['unid']}.html"
    save_text(detail_raw_path, detail_html)
    product_payload, nutrients = parse_nlc_detail_html(detail_html, item["unid"])
    product_payload["detail_url"] = item["detail_url"]
    product_payload["raw_html_path"] = str(detail_raw_path)
    product_payload["source_list_page"] = page
    return product_payload, nutrients


def crawl_nlc(args: argparse.Namespace) -> None:
    ensure_directories()
    source = load_sources()["chinanutri_nlc"]
    session = build_session()
    conn = create_connection(args.db_path)
    init_schema(conn)
    register_source(conn, source)

    try:
        page = args.start_page
        crawled_pages = 0
        while True:
            if args.max_pages and crawled_pages >= args.max_pages:
                break
            list_url = NLC_LIST_URL_TEMPLATE.format(page=page)
            print(f"[nlc] list page {page}")
            html = fetch_text(session, list_url, referer=source["home_url"])
            raw_path = RAW_DIR / "chinanutri_nlc" / "pages" / f"page_{page:06d}.html"
            save_text(raw_path, html)
            items, has_next = parse_nlc_list_page(html)
            if not items:
                print(f"[nlc] stop at page {page}: no products")
                break
            for item in items:
                upsert_nlc_product(
                    conn,
                    {
                        "unid": item["unid"],
                        "product_name": item["product_name"],
                        "detail_url": item["detail_url"],
                        "image_url": item["image_url"],
                        "source_list_page": page,
                    },
                )
            conn.commit()

            if not args.skip_details:
                if args.detail_workers <= 1:
                    for index, item in enumerate(items, start=1):
                        print(f"[nlc] detail page {page} item {index}/{len(items)}: {item['unid']}")
                        product_payload, nutrients = fetch_nlc_detail_bundle(item, list_url, page)
                        upsert_nlc_product(conn, product_payload)
                        replace_nlc_product_nutrients(conn, item["unid"], nutrients)
                        conn.commit()
                else:
                    futures: dict[concurrent.futures.Future, tuple[int, dict]] = {}
                    with concurrent.futures.ThreadPoolExecutor(max_workers=args.detail_workers) as executor:
                        for index, item in enumerate(items, start=1):
                            print(f"[nlc] queue detail page {page} item {index}/{len(items)}: {item['unid']}")
                            future = executor.submit(fetch_nlc_detail_bundle, item, list_url, page)
                            futures[future] = (index, item)
                        for future in concurrent.futures.as_completed(futures):
                            index, item = futures[future]
                            print(f"[nlc] detail done page {page} item {index}/{len(items)}: {item['unid']}")
                            product_payload, nutrients = future.result()
                            upsert_nlc_product(conn, product_payload)
                            replace_nlc_product_nutrients(conn, item["unid"], nutrients)
                            conn.commit()

            crawled_pages += 1
            if not has_next:
                print(f"[nlc] stop at page {page}: no next page")
                break
            page += 1

        build_unified_catalog(conn)
        stats = write_stats(conn, args.stats_path)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    finally:
        conn.close()


def fatsecret_brand_type_label(brand_type: int) -> str:
    labels = {
        1: "manufacturer",
        2: "restaurant_chain",
        3: "retailer",
    }
    return labels.get(brand_type, "unknown")


def parse_fatsecret_brand_directory_page(html: str, brand_type: int, letter: str, directory_page: int) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    brand_map: dict[str, dict] = {}
    for link in soup.select("a[href]"):
        href = link.get("href", "").strip()
        if not href.startswith("/%E7%83%AD%E9%87%8F%E8%90%A5%E5%85%BB/"):
            continue
        if "/search?q=" in href:
            continue
        text = " ".join(link.get_text(" ", strip=True).split())
        if not text:
            continue
        parts = href.split("?")[0].strip("/").split("/")
        if len(parts) != 2:
            continue
        brand_slug = parts[1]
        brand_map[brand_slug] = {
            "brand_slug": brand_slug,
            "brand_name": text,
            "brand_url": urljoin(FATSECRET_DETAIL_BASE, href),
            "archive_url": urljoin(FATSECRET_DETAIL_BASE, "/%e5%ad%98%e6%a1%a3/" + href.lstrip("/")),
            "brand_type": brand_type,
            "brand_type_label": fatsecret_brand_type_label(brand_type),
            "directory_letter": letter,
            "directory_page": directory_page,
            "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    return sorted(brand_map.values(), key=lambda item: (item["brand_name"], item["brand_slug"]))


def discover_fatsecret_brands(session: requests.Session, conn: sqlite3.Connection, source: dict) -> list[dict]:
    letters = "abcdefghijklmnopqrstuvwxyz*"
    discovered: dict[str, dict] = {}
    for brand_type in (1, 2, 3):
        for letter in letters:
            letter_token = "star" if letter == "*" else letter
            first_url = FATSECRET_BRANDS_URL_TEMPLATE.format(letter=letter, brand_type=brand_type)
            print(f"[fatsecret] directory type={brand_type} letter={letter}")
            first_html = fetch_text_retrying(session, first_url, referer=source["home_url"])
            first_path = RAW_DIR / "fatsecret_cn" / "brands" / f"type_{brand_type}_{letter_token}_page_001.html"
            save_text(first_path, first_html)
            soup = BeautifulSoup(first_html, "lxml")
            page_indexes = {0}
            for link in soup.select("a[href]"):
                href = link.get("href", "")
                match = re.search(r"pa=brands&pg=(\d+)&f=", href)
                if match:
                    page_indexes.add(int(match.group(1)))

            for page_index in sorted(page_indexes):
                if page_index == 0:
                    html = first_html
                else:
                    page_url = FATSECRET_BRANDS_PAGE_URL_TEMPLATE.format(letter=letter, brand_type=brand_type, page_index=page_index)
                    html = fetch_text_retrying(session, page_url, referer=first_url)
                    page_path = RAW_DIR / "fatsecret_cn" / "brands" / f"type_{brand_type}_{letter_token}_page_{page_index + 1:03d}.html"
                    save_text(page_path, html)
                page_items = parse_fatsecret_brand_directory_page(html, brand_type, letter, page_index + 1)
                for item in page_items:
                    discovered[item["brand_slug"]] = item
                    upsert_fatsecret_brand(conn, item)
                conn.commit()

    return sorted(discovered.values(), key=lambda item: (item["brand_type"], normalize_text(item["brand_name"])))


def parse_fatsecret_search_summary(summary_text: str | None) -> dict:
    if not summary_text:
        return {
            "search_summary_text": None,
            "serving_description": None,
            "energy_kcal": None,
            "protein_g": None,
            "fat_g": None,
            "carb_g": None,
        }
    compact = " ".join(summary_text.split())
    compact = compact.split("营养成分")[0].strip()
    match = re.search(
        r"^每(?P<serving>.+?)\s*-\s*卡路里:\s*(?P<kcal>[\d.]+)千卡\s*\|\s*脂肪:\s*(?P<fat>[\d.]+)克\s*\|\s*碳水物:\s*(?P<carb>[\d.]+)克\s*\|\s*蛋白质:\s*(?P<protein>[\d.]+)克",
        compact,
    )
    if not match:
        return {
            "search_summary_text": compact,
            "serving_description": None,
            "energy_kcal": None,
            "protein_g": None,
            "fat_g": None,
            "carb_g": None,
        }
    return {
        "search_summary_text": compact,
        "serving_description": match.group("serving").strip(),
        "energy_kcal": float(match.group("kcal")),
        "protein_g": float(match.group("protein")),
        "fat_g": float(match.group("fat")),
        "carb_g": float(match.group("carb")),
    }


def parse_fatsecret_search_page(html: str, query_text: str, source_page: int) -> tuple[int, int, list[dict]]:
    soup = BeautifulSoup(html, "lxml")
    summary_node = soup.select_one("div.searchResultSummary")
    total_results = 0
    if summary_node:
        summary_text = " ".join(summary_node.get_text(" ", strip=True).split())
        match = re.search(r"总共\s*([\d,]+)", summary_text)
        if match:
            total_results = int(match.group(1).replace(",", ""))
    total_pages = math.ceil(total_results / 10) if total_results else 0

    rows: list[dict] = []
    for rank, td in enumerate(soup.select("table.generic.searchResult td.borderBottom"), start=1):
        product_link = td.select_one("a.prominent[href]")
        if product_link is None:
            continue
        brand_link = td.select_one("a.brand[href]")
        summary_div = td.select_one("div.smallText.greyText.greyLink")
        detail_url = urljoin(FATSECRET_DETAIL_BASE, product_link.get("href", ""))
        brand_url = urljoin(FATSECRET_DETAIL_BASE, brand_link.get("href", "")) if brand_link else None
        brand_slug = None
        if brand_url:
            parts = brand_url.rstrip("/").split("/")
            brand_slug = parts[-1] if parts else None
        product_name = " ".join(product_link.get_text(" ", strip=True).split())
        brand_name = None
        if brand_link:
            brand_name = " ".join(brand_link.get_text(" ", strip=True).split()).strip("() ")
        summary_data = parse_fatsecret_search_summary(summary_div.get_text(" ", strip=True) if summary_div else None)
        serving = parse_serving_info(summary_data["serving_description"])
        rows.append(
            {
                "detail_url": detail_url,
                "brand_slug": brand_slug,
                "brand_name": brand_name,
                "product_name": product_name,
                "source_query": query_text,
                "source_page": source_page,
                "source_rank": rank,
                "archived": 0,
                "search_summary_text": summary_data["search_summary_text"],
                "serving_description": serving.raw,
                "serving_amount_numeric": serving.amount_numeric,
                "serving_amount_unit": serving.amount_unit,
                "normalized_basis": serving.normalized_basis,
                "energy_kcal": summary_data["energy_kcal"],
                "protein_g": summary_data["protein_g"],
                "fat_g": summary_data["fat_g"],
                "carb_g": summary_data["carb_g"],
                "energy_kcal_100g": normalize_per_100(summary_data["energy_kcal"], serving),
                "protein_g_100g": normalize_per_100(summary_data["protein_g"], serving),
                "fat_g_100g": normalize_per_100(summary_data["fat_g"], serving),
                "carb_g_100g": normalize_per_100(summary_data["carb_g"], serving),
                "discovered_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return total_results, total_pages, rows


def crawl_fatsecret_query_pages(
    conn: sqlite3.Connection,
    session: requests.Session,
    *,
    query_text: str,
    raw_dir_name: str,
    referer: str,
    max_search_pages: int | None,
    target_total_records: int | None,
) -> tuple[int, int]:
    encoded_query = quote(query_text)
    first_url = FATSECRET_SEARCH_URL_TEMPLATE.format(query=encoded_query)
    search_dir = RAW_DIR / "fatsecret_cn" / "search" / raw_dir_name
    first_html = fetch_text_retrying(session, first_url, referer=referer)
    save_text(search_dir / "page_001.html", first_html)
    total_results, total_pages, rows = parse_fatsecret_search_page(first_html, query_text, 1)
    if max_search_pages:
        total_pages = min(total_pages, max_search_pages)
    for row in rows:
        upsert_fatsecret_product(conn, row)
    conn.commit()
    print(f"[fatsecret] search page 1/{max(total_pages, 1)} rows={len(rows)} total_results={total_results} query={query_text}")
    if target_total_records and fatsecret_total_records(conn) >= target_total_records:
        return total_results, 1
    previous_unique_count = query_table_count(conn, "fatsecret_products")
    no_growth_pages = 0
    pages_crawled = 1 if total_pages else 0
    for page_num in range(2, total_pages + 1):
        page_url = first_url + f"&pg={page_num - 1}"
        html = fetch_text_retrying(session, page_url, referer=first_url)
        save_text(search_dir / f"page_{page_num:03d}.html", html)
        _, _, rows = parse_fatsecret_search_page(html, query_text, page_num)
        for row in rows:
            upsert_fatsecret_product(conn, row)
        conn.commit()
        pages_crawled = page_num
        current_unique_count = query_table_count(conn, "fatsecret_products")
        if current_unique_count <= previous_unique_count:
            no_growth_pages += 1
        else:
            no_growth_pages = 0
        previous_unique_count = current_unique_count
        print(f"[fatsecret] search page {page_num}/{total_pages} rows={len(rows)} unique_products={current_unique_count} query={query_text}")
        if target_total_records and fatsecret_total_records(conn) >= target_total_records:
            break
        if no_growth_pages >= FATSECRET_NO_GROWTH_PAGE_LIMIT:
            print(f"[fatsecret] stop early no growth for {no_growth_pages} pages query={query_text}")
            break
    return total_results, pages_crawled


def extract_keyword_candidates(text: str) -> Iterable[str]:
    stop_terms = {
        "营养", "食品", "产品", "原味", "口味", "系列", "经典", "低糖", "无糖",
        "即食", "每日", "健康", "中国", "热量", "食物", "品牌", "查询", "系统",
    }
    cleaned = re.sub(r"[（(].*?[）)]", " ", text)
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", " ", cleaned)
    for segment in re.findall(r"[\u4e00-\u9fff]{2,}", cleaned):
        segment = segment.strip()
        if not segment or segment in stop_terms:
            continue
        if 2 <= len(segment) <= 8:
            yield segment
            continue
        emitted = False
        for food_term in FATSECRET_FOOD_TERMS:
            if food_term in segment and food_term not in stop_terms:
                emitted = True
                yield food_term
        suffix_match = re.search(r"(蛋白粉|乳清|增肌粉|代餐|燕麦片|燕麦|麦片|米糊|米粉|牛奶|酸奶|豆浆|面包|吐司|饼干|饮料|咖啡|巧克力)$", segment)
        if suffix_match:
            emitted = True
            yield suffix_match.group(1)
        if not emitted and len(segment) <= 12:
            yield segment
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+.'-]{2,14}", cleaned):
        normalized = token.strip().casefold()
        if normalized not in {"food", "foods", "milk", "drink"}:
            yield token


def derive_fatsecret_keyword_seeds(conn: sqlite3.Connection, limit: int) -> list[str]:
    counter: Counter[str] = Counter()
    priority_terms = [
        "蛋白粉", "乳清", "增肌粉", "代餐", "燕麦", "麦片", "米糊", "米粉", "牛奶", "酸奶",
        "面包", "咖啡", "豆浆", "鸡胸", "鸡蛋", "能量棒", "奶昔", "饼干", "巧克力", "饮料",
    ]
    for term in priority_terms:
        counter[term] += 10_000

    name_queries = [
        ("SELECT product_name FROM nlc_products", None),
        ("SELECT food_name FROM fq_food_list", None),
        ("SELECT product_name FROM fatsecret_products", None),
    ]
    for sql, params in name_queries:
        for row in conn.execute(sql, params or ()):
            name = row[0]
            if not name:
                continue
            for token in extract_keyword_candidates(name):
                counter[token] += 1

    completed = {
        row[0]
        for row in conn.execute("SELECT term FROM fatsecret_search_terms WHERE completed_at IS NOT NULL")
    }
    seeds: list[str] = []
    for token, _count in counter.most_common():
        if token in completed:
            continue
        if token not in seeds:
            seeds.append(token)
        if len(seeds) >= limit:
            break
    return seeds


def dedupe_terms(terms: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw_term in terms:
        term = " ".join((raw_term or "").split()).strip()
        if not term or term in seen:
            continue
        seen.add(term)
        ordered.append(term)
    return ordered


def load_keyword_terms_file(path: Path) -> list[str]:
    terms: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        for candidate in re.split(r"[,，]", line):
            candidate = candidate.strip()
            if candidate:
                terms.append(candidate)
    return dedupe_terms(terms)


def collect_fatsecret_keyword_seeds(conn: sqlite3.Connection, args: argparse.Namespace) -> list[str]:
    explicit_terms: list[str] = []
    if getattr(args, "keyword_terms_file", None):
        explicit_terms.extend(load_keyword_terms_file(args.keyword_terms_file))
    if getattr(args, "keyword_terms", None):
        explicit_terms.extend(args.keyword_terms)
    explicit_terms = dedupe_terms(explicit_terms)

    if explicit_terms and getattr(args, "skip_derived_keywords", False):
        return explicit_terms

    derived_terms = derive_fatsecret_keyword_seeds(conn, args.max_keyword_terms) if args.max_keyword_terms else []
    return dedupe_terms(explicit_terms + derived_terms)


def parse_fatsecret_detail_html(html: str, detail_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    nutrition_panel = soup.select_one("div.nutrition_facts")
    brand_link = soup.select_one("h2.manufacturer a")
    product_title = soup.select_one("div.summarypanelcontent h1")
    payload: dict[str, object] = {
        "detail_url": detail_url,
        "brand_name": " ".join(brand_link.get_text(" ", strip=True).split()) if brand_link else None,
        "product_name": " ".join(product_title.get_text(" ", strip=True).split()) if product_title else None,
        "detail_crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if brand_link:
        payload["brand_slug"] = brand_link.get("href", "").strip("/").split("/")[-1]

    if nutrition_panel:
        serving_value = nutrition_panel.select_one("div.serving_size_value")
        serving = parse_serving_info(serving_value.get_text(" ", strip=True) if serving_value else None)
        payload["serving_description"] = serving.raw
        payload["serving_amount_numeric"] = serving.amount_numeric
        payload["serving_amount_unit"] = serving.amount_unit
        payload["normalized_basis"] = serving.normalized_basis

        nutrient_values: dict[str, str] = {}
        current_label: str | None = None
        for node in nutrition_panel.find_all("div", class_=re.compile(r"\bnutrient\b"), recursive=False):
            classes = node.get("class", [])
            text = " ".join(node.get_text(" ", strip=True).split())
            if "left" in classes:
                current_label = text
                continue
            if "right" in classes:
                if current_label:
                    nutrient_values[current_label] = text
                elif text.endswith("千卡"):
                    nutrient_values["千卡"] = text
                current_label = None

        energy_kj = parse_amount(nutrient_values.get("能源"))
        energy_kcal = parse_amount(nutrient_values.get("千卡"))
        protein = parse_amount(nutrient_values.get("蛋白质"))
        fat = parse_amount(nutrient_values.get("脂肪"))
        saturated_fat = parse_amount(nutrient_values.get("饱和脂肪"))
        carb = parse_amount(nutrient_values.get("碳水化合物"))
        sugar = parse_amount(nutrient_values.get("糖"))

        payload["energy_kj_raw"] = energy_kj.raw
        payload["energy_kj"] = energy_kj.numeric
        payload["energy_kcal"] = energy_kcal.numeric
        payload["protein_g"] = protein.numeric
        payload["fat_g"] = fat.numeric
        payload["saturated_fat_g"] = saturated_fat.numeric
        payload["carb_g"] = carb.numeric
        payload["sugar_g"] = sugar.numeric
        payload["energy_kj_100g"] = normalize_per_100(energy_kj.numeric, serving)
        payload["energy_kcal_100g"] = normalize_per_100(energy_kcal.numeric, serving)
        payload["protein_g_100g"] = normalize_per_100(protein.numeric, serving)
        payload["fat_g_100g"] = normalize_per_100(fat.numeric, serving)
        payload["saturated_fat_g_100g"] = normalize_per_100(saturated_fat.numeric, serving)
        payload["carb_g_100g"] = normalize_per_100(carb.numeric, serving)
        payload["sugar_g_100g"] = normalize_per_100(sugar.numeric, serving)

    for node in soup.select("td.smallText, div.smallText"):
        text = " ".join(node.get_text(" ", strip=True).split())
        if text.startswith("上次更新时间:"):
            payload["last_updated_at"] = text.replace("上次更新时间:", "", 1).strip()
        elif text.startswith("源:"):
            payload["detail_source"] = text.replace("源:", "", 1).strip()

    return payload


def fetch_fatsecret_detail_bundle(detail_url: str) -> dict:
    session = get_thread_session()
    html = fetch_text_retrying(session, detail_url, referer=detail_url)
    detail_key = safe_filename(detail_url.replace(FATSECRET_DETAIL_BASE + "/", ""))[:180]
    raw_path = RAW_DIR / "fatsecret_cn" / "details" / f"{detail_key}.html"
    save_text(raw_path, html)
    payload = parse_fatsecret_detail_html(html, detail_url)
    payload["raw_detail_html_path"] = str(raw_path)
    return payload


def fatsecret_total_records(conn: sqlite3.Connection) -> int:
    total = 0
    for table_name in ("fq_food_list", "nlc_products", "fatsecret_products"):
        if table_exists(conn, table_name):
            total += query_table_count(conn, table_name)
    return total


def crawl_fatsecret(args: argparse.Namespace) -> None:
    ensure_directories()
    source = load_sources()["fatsecret_cn"]
    session = build_session()
    conn = create_connection(args.db_path)
    init_schema(conn)
    register_source(conn, source)

    try:
        if not args.skip_brands:
            brands = discover_fatsecret_brands(session, conn, source)
            if args.max_brands:
                brands = brands[: args.max_brands]

            total_brands = len(brands)
            for index, brand in enumerate(brands, start=1):
                if args.target_total_records and fatsecret_total_records(conn) >= args.target_total_records:
                    print(f"[fatsecret] target reached: {fatsecret_total_records(conn)}")
                    break
                if conn.execute(
                    "SELECT search_completed_at FROM fatsecret_brands WHERE brand_slug = ?",
                    (brand["brand_slug"],),
                ).fetchone()[0]:
                    continue

                query = brand["brand_name"]
                print(f"[fatsecret] brand {index}/{total_brands}: {query}")
                total_results, total_pages = crawl_fatsecret_query_pages(
                    conn,
                    session,
                    query_text=query,
                    raw_dir_name=safe_filename(brand["brand_slug"]),
                    referer=brand["brand_url"],
                    max_search_pages=args.max_search_pages_per_brand,
                    target_total_records=args.target_total_records,
                )
                if args.target_total_records and fatsecret_total_records(conn) >= args.target_total_records:
                    conn.execute(
                        """
                        UPDATE fatsecret_brands
                        SET search_total_results = ?, search_pages_crawled = ?, search_completed_at = datetime('now'), crawled_at = datetime('now')
                        WHERE brand_slug = ?
                        """,
                        (total_results, total_pages, brand["brand_slug"]),
                    )
                    conn.commit()
                    break

                conn.execute(
                    """
                    UPDATE fatsecret_brands
                    SET search_total_results = ?, search_pages_crawled = ?, search_completed_at = datetime('now'), crawled_at = datetime('now')
                    WHERE brand_slug = ?
                    """,
                    (total_results, total_pages, brand["brand_slug"]),
                )
                conn.commit()

        keyword_seeds = collect_fatsecret_keyword_seeds(conn, args)
        should_run_keywords = bool(keyword_seeds) and (
            not args.target_total_records or fatsecret_total_records(conn) < args.target_total_records
        )
        if should_run_keywords:
            for keyword_index, term in enumerate(keyword_seeds, start=1):
                if args.target_total_records and fatsecret_total_records(conn) >= args.target_total_records:
                    print(f"[fatsecret] keyword target reached: {fatsecret_total_records(conn)}")
                    break
                term_row = conn.execute(
                    "SELECT completed_at FROM fatsecret_search_terms WHERE term = ?",
                    (term,),
                ).fetchone()
                if term_row and term_row[0]:
                    continue
                print(f"[fatsecret] keyword {keyword_index}/{len(keyword_seeds)}: {term}")
                total_results, total_pages = crawl_fatsecret_query_pages(
                    conn,
                    session,
                    query_text=term,
                    raw_dir_name="kw_" + safe_filename(term),
                    referer=source["home_url"],
                    max_search_pages=args.max_search_pages_per_brand,
                    target_total_records=args.target_total_records,
                )
                upsert_fatsecret_search_term(
                    conn,
                    {
                        "term": term,
                        "source_kind": "keyword_seed",
                        "total_results": total_results,
                        "pages_crawled": total_pages,
                        "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "crawled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    },
                )
                conn.commit()

        if not args.skip_details:
            pending_rows = conn.execute(
                """
                SELECT detail_url, product_name
                FROM fatsecret_products
                WHERE detail_crawled_at IS NULL
                """
            ).fetchall()
            pending = [(row[0], row[1] or "") for row in pending_rows]
            pending.sort(key=lambda item: (0 if FATSECRET_PRIORITY_PATTERN.search(item[1] or "") else 1, item[1]))
            if args.detail_limit:
                pending = pending[: args.detail_limit]
            if args.detail_workers <= 1:
                for item_index, (detail_url, _product_name) in enumerate(pending, start=1):
                    print(f"[fatsecret] detail {item_index}/{len(pending)}: {detail_url}")
                    payload = fetch_fatsecret_detail_bundle(detail_url)
                    upsert_fatsecret_product(conn, payload)
                    conn.commit()
            else:
                futures: dict[concurrent.futures.Future, str] = {}
                with concurrent.futures.ThreadPoolExecutor(max_workers=args.detail_workers) as executor:
                    for detail_url, _product_name in pending:
                        futures[executor.submit(fetch_fatsecret_detail_bundle, detail_url)] = detail_url
                    for item_index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
                        payload = future.result()
                        upsert_fatsecret_product(conn, payload)
                        conn.commit()
                        print(f"[fatsecret] detail {item_index}/{len(futures)}: {futures[future]}")

        build_unified_catalog(conn)
        stats = write_stats(conn, args.stats_path)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    finally:
        conn.close()


def build_unified_catalog(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS china_food_catalog;
        CREATE TABLE china_food_catalog AS
        SELECT
            'chinanutri_fq' AS source,
            CAST(food_id AS TEXT) AS source_food_id,
            food_name AS name,
            other_name AS alias_name,
            NULL AS brand,
            category_one_name AS category_top,
            category_two_name AS category_sub,
            'basic_food' AS food_type,
            energy_kj_100g,
            energy_kcal_100g,
            protein_g_100g,
            fat_g_100g,
            carb_g_100g,
            fiber_g_100g,
            sodium_mg_100g,
            cholesterol_mg_100g,
            calcium_mg_100g,
            potassium_mg_100g,
            iron_mg_100g,
            zinc_mg_100g,
            vitamin_c_mg_100g,
            NULL AS manufacturer,
            NULL AS barcode,
            NULL AS ingredients,
            detail_url
        FROM fq_food_list

        UNION ALL

        SELECT
            'chinanutri_nlc' AS source,
            unid AS source_food_id,
            product_name AS name,
            NULL AS alias_name,
            brand,
            food_category AS category_top,
            NULL AS category_sub,
            'packaged_food' AS food_type,
            energy_kj_100g,
            energy_kcal_100g,
            protein_g_100g,
            fat_g_100g,
            carb_g_100g,
            NULL AS fiber_g_100g,
            sodium_mg_100g,
            NULL AS cholesterol_mg_100g,
            NULL AS calcium_mg_100g,
            NULL AS potassium_mg_100g,
            NULL AS iron_mg_100g,
            NULL AS zinc_mg_100g,
            NULL AS vitamin_c_mg_100g,
            manufacturer,
            barcode,
            ingredients,
            detail_url
        FROM nlc_products

        UNION ALL

        SELECT
            'fatsecret_cn' AS source,
            detail_url AS source_food_id,
            product_name AS name,
            NULL AS alias_name,
            fatsecret_products.brand_name AS brand,
            fatsecret_brands.brand_type_label AS category_top,
            normalized_basis AS category_sub,
            'market_food' AS food_type,
            COALESCE(energy_kj_100g, energy_kj) AS energy_kj_100g,
            COALESCE(energy_kcal_100g, energy_kcal) AS energy_kcal_100g,
            COALESCE(protein_g_100g, protein_g) AS protein_g_100g,
            COALESCE(fat_g_100g, fat_g) AS fat_g_100g,
            COALESCE(carb_g_100g, carb_g) AS carb_g_100g,
            NULL AS fiber_g_100g,
            sodium_mg_100g,
            NULL AS cholesterol_mg_100g,
            NULL AS calcium_mg_100g,
            NULL AS potassium_mg_100g,
            NULL AS iron_mg_100g,
            NULL AS zinc_mg_100g,
            NULL AS vitamin_c_mg_100g,
            NULL AS manufacturer,
            NULL AS barcode,
            NULL AS ingredients,
            detail_url
        FROM fatsecret_products
        LEFT JOIN fatsecret_brands
          ON fatsecret_brands.brand_slug = fatsecret_products.brand_slug;

        CREATE INDEX IF NOT EXISTS idx_china_food_catalog_source ON china_food_catalog(source);
        CREATE INDEX IF NOT EXISTS idx_china_food_catalog_name ON china_food_catalog(name);
        """
    )
    if table_exists(conn, "china_food_catalog_fts"):
        conn.execute("DROP TABLE china_food_catalog_fts")
    conn.execute(
        """
        CREATE VIRTUAL TABLE china_food_catalog_fts USING fts5(
            source_food_id,
            name,
            alias_name,
            brand,
            category_top,
            category_sub,
            manufacturer,
            barcode,
            ingredients,
            content='china_food_catalog',
            content_rowid='rowid'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO china_food_catalog_fts(
            rowid, source_food_id, name, alias_name, brand, category_top, category_sub, manufacturer, barcode, ingredients
        )
        SELECT rowid, source_food_id, name, alias_name, brand, category_top, category_sub, manufacturer, barcode, ingredients
        FROM china_food_catalog
        """
    )
    conn.commit()


def query_table_count(conn: sqlite3.Connection, table_name: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def write_stats(conn: sqlite3.Connection, destination: Path) -> dict:
    stats = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tables": {},
    }
    for table_name in [
        "fq_categories",
        "fq_food_list",
        "fq_food_details",
        "fq_food_nutrients",
        "nlc_products",
        "nlc_product_nutrients",
        "fatsecret_brands",
        "fatsecret_products",
        "fatsecret_search_terms",
        "china_food_catalog",
    ]:
        if table_exists(conn, table_name):
            stats["tables"][table_name] = query_table_count(conn, table_name)
    if table_exists(conn, "source_registry"):
        rows = conn.execute(
            "SELECT source_key, source_name, provider, home_url, license_note, last_crawled_at FROM source_registry ORDER BY source_key"
        ).fetchall()
        stats["sources"] = [
            {
                "source_key": row[0],
                "source_name": row[1],
                "provider": row[2],
                "home_url": row[3],
                "license_note": row[4],
                "last_crawled_at": row[5],
            }
            for row in rows
        ]
    destination.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def run_stats(args: argparse.Namespace) -> None:
    conn = create_connection(args.db_path)
    init_schema(conn)
    try:
        stats = write_stats(conn, args.stats_path)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a China-focused nutrition database from public Chinanutri sources.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fq_parser = subparsers.add_parser("crawl-fq", help="Crawl the public food composition query platform.")
    fq_parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    fq_parser.add_argument("--stats-path", type=Path, default=DEFAULT_STATS_PATH)
    fq_parser.add_argument("--max-categories", type=int, default=None)
    fq_parser.add_argument("--max-pages-per-category", type=int, default=None)
    fq_parser.add_argument("--skip-details", action="store_true")
    fq_parser.add_argument("--max-details", type=int, default=None)
    fq_parser.set_defaults(func=crawl_fq)

    nlc_parser = subparsers.add_parser("crawl-nlc", help="Crawl the public packaged-food nutrition label site.")
    nlc_parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    nlc_parser.add_argument("--stats-path", type=Path, default=DEFAULT_STATS_PATH)
    nlc_parser.add_argument("--start-page", type=int, default=1)
    nlc_parser.add_argument("--max-pages", type=int, default=None)
    nlc_parser.add_argument("--skip-details", action="store_true")
    nlc_parser.add_argument("--detail-workers", type=int, default=1)
    nlc_parser.set_defaults(func=crawl_nlc)

    fatsecret_parser = subparsers.add_parser("crawl-fatsecret", help="Crawl the public FatSecret China food directory.")
    fatsecret_parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    fatsecret_parser.add_argument("--stats-path", type=Path, default=DEFAULT_STATS_PATH)
    fatsecret_parser.add_argument("--skip-brands", action="store_true")
    fatsecret_parser.add_argument("--max-brands", type=int, default=None)
    fatsecret_parser.add_argument("--max-search-pages-per-brand", type=int, default=None)
    fatsecret_parser.add_argument("--max-keyword-terms", type=int, default=600)
    fatsecret_parser.add_argument("--keyword-terms-file", type=Path, default=None)
    fatsecret_parser.add_argument("--keyword-term", dest="keyword_terms", action="append", default=None)
    fatsecret_parser.add_argument("--skip-derived-keywords", action="store_true")
    fatsecret_parser.add_argument("--target-total-records", type=int, default=None)
    fatsecret_parser.add_argument("--skip-details", action="store_true")
    fatsecret_parser.add_argument("--detail-limit", type=int, default=None)
    fatsecret_parser.add_argument("--detail-workers", type=int, default=1)
    fatsecret_parser.set_defaults(func=crawl_fatsecret)

    stats_parser = subparsers.add_parser("stats", help="Write and print stats for the China nutrition database.")
    stats_parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    stats_parser.add_argument("--stats-path", type=Path, default=DEFAULT_STATS_PATH)
    stats_parser.set_defaults(func=run_stats)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
