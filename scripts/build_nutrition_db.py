from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import sqlite3
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "sources.json"
DATA_ROOT = Path(os.environ.get("NUTRITION_DATA_ROOT", r"E:\爬虫抓包数据"))
RAW_DIR = DATA_ROOT / "raw"
PROCESSED_DIR = DATA_ROOT / "processed"
DEFAULT_DB_PATH = PROCESSED_DIR / "nutrition.db"
DEFAULT_STATS_PATH = PROCESSED_DIR / "stats.json"

DEFAULT_SOURCES: list[str] = []
DOWNLOAD_CHUNK_SIZE = 1024 * 1024 * 4
SQLITE_BATCH_SIZE = 5000

USDA_INTERESTING_NUTRIENTS = {
    "energy_kcal_100g": {
        "ids": {"1008"},
        "numbers": {"208"},
        "names": {"energy"},
        "units": {"kcal"},
    },
    "protein_g_100g": {
        "ids": {"1003"},
        "numbers": {"203"},
        "names": {"protein"},
        "units": {"g"},
    },
    "fat_g_100g": {
        "ids": {"1004"},
        "numbers": {"204"},
        "names": {"total lipid (fat)", "fat"},
        "units": {"g"},
    },
    "carb_g_100g": {
        "ids": {"1005"},
        "numbers": {"205", "205.2"},
        "names": {"carbohydrate, by difference", "carbohydrate"},
        "units": {"g"},
    },
    "fiber_g_100g": {
        "ids": {"1079", "2033"},
        "numbers": {"291", "293"},
        "names": {"fiber, total dietary", "total dietary fiber (aoac 2011.25)"},
        "units": {"g"},
    },
    "sugar_g_100g": {
        "ids": {"1063", "2000"},
        "numbers": {"269", "269.3"},
        "names": {"sugars, total", "total sugars"},
        "units": {"g"},
    },
    "saturated_fat_g_100g": {
        "ids": {"1258", "1326"},
        "numbers": {"606", "690"},
        "names": {"fatty acids, total saturated", "fatty acids, total sat., nlea"},
        "units": {"g"},
    },
    "sodium_mg_100g": {
        "ids": {"1093"},
        "numbers": {"307"},
        "names": {"sodium, na", "sodium"},
        "units": {"mg"},
    },
}

OFF_SELECTED_COLUMNS = [
    "code",
    "product_name",
    "generic_name",
    "brands",
    "quantity",
    "serving_size",
    "categories",
    "categories_tags",
    "main_category",
    "main_category_en",
    "countries",
    "countries_tags",
    "ingredients_text",
    "ingredients_text_en",
    "nutrition_grades",
    "nova_group",
    "ecoscore_grade",
    "pnns_groups_1",
    "pnns_groups_2",
    "food_groups",
    "food_groups_tags",
    "image_url",
    "image_front_url",
    "energy-kcal_100g",
    "energy_100g",
    "fat_100g",
    "saturated-fat_100g",
    "carbohydrates_100g",
    "sugars_100g",
    "fiber_100g",
    "proteins_100g",
    "salt_100g",
    "sodium_100g",
]


def load_sources() -> dict[str, dict]:
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {item["key"]: item for item in payload["sources"]}


def ensure_directories() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def head_metadata(url: str) -> dict[str, str | None]:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "nutrition-db-builder/0.1"})
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return {
                    "content_length": response.headers.get("Content-Length"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "content_type": response.headers.get("Content-Type"),
                }
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            print(f"[head] retry {attempt}/5 for {url}: {exc}")
            time.sleep(min(attempt * 2, 10))
    print(f"[head] giving up on metadata for {url}: {last_error}")
    return {"content_length": None, "last_modified": None, "content_type": None}


def download_file(url: str, destination: Path, force: bool = False) -> Path:
    ensure_directories()
    metadata = head_metadata(url)
    total = metadata.get("content_length")
    total_bytes = int(total) if total and str(total).isdigit() else None
    tmp_path = destination.with_suffix(destination.suffix + ".part")

    if force:
        destination.unlink(missing_ok=True)
        tmp_path.unlink(missing_ok=True)

    if destination.exists() and total_bytes and destination.stat().st_size == total_bytes:
        print(f"[download] skip existing {destination.name}")
        return destination

    if destination.exists() and not tmp_path.exists():
        destination.replace(tmp_path)

    started = time.time()
    attempts = 0
    while True:
        attempts += 1
        existing_bytes = tmp_path.stat().st_size if tmp_path.exists() else 0
        if total_bytes and existing_bytes == total_bytes:
            break
        if attempts > 10:
            raise RuntimeError(f"Download failed after {attempts - 1} attempts: {destination.name}")

        headers = {"User-Agent": "nutrition-db-builder/0.1"}
        if existing_bytes:
            headers["Range"] = f"bytes={existing_bytes}-"
        request = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(request, timeout=60) as response:
            mode = "ab" if existing_bytes and getattr(response, "status", None) == 206 else "wb"
            if mode == "wb":
                existing_bytes = 0
            downloaded = existing_bytes
            with tmp_path.open(mode) as handle:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if total_bytes:
                        pct = downloaded / total_bytes * 100
                        mb = downloaded / 1024 / 1024
                        total_mb = total_bytes / 1024 / 1024
                        print(f"\r[download] {destination.name}: {mb:.1f}/{total_mb:.1f} MB ({pct:.1f}%)", end="", flush=True)
                    else:
                        mb = downloaded / 1024 / 1024
                        print(f"\r[download] {destination.name}: {mb:.1f} MB", end="", flush=True)
        current_size = tmp_path.stat().st_size if tmp_path.exists() else 0
        if not total_bytes or current_size == total_bytes:
            break
        print(f"\n[download] retrying {destination.name} from byte {current_size:,}")

    elapsed = time.time() - started
    print()
    tmp_path.replace(destination)
    print(f"[download] saved {destination} in {elapsed:.1f}s")
    return destination


def q(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def create_connection(db_path: Path) -> sqlite3.Connection:
    ensure_directories()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -200000")
    return conn


def create_metadata_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS source_registry (
            key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            url TEXT NOT NULL,
            filename TEXT NOT NULL,
            format TEXT NOT NULL,
            update_frequency TEXT,
            license_note TEXT,
            downloaded_at TEXT,
            imported_at TEXT,
            content_length TEXT,
            last_modified TEXT
        );
        """
    )
    conn.commit()


def register_source_download(conn: sqlite3.Connection, source: dict, metadata: dict[str, str | None]) -> None:
    conn.execute(
        """
        INSERT INTO source_registry (
            key, name, provider, url, filename, format, update_frequency, license_note,
            downloaded_at, content_length, last_modified
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            name = excluded.name,
            provider = excluded.provider,
            url = excluded.url,
            filename = excluded.filename,
            format = excluded.format,
            update_frequency = excluded.update_frequency,
            license_note = excluded.license_note,
            downloaded_at = excluded.downloaded_at,
            content_length = excluded.content_length,
            last_modified = excluded.last_modified
        """,
        (
            source["key"],
            source["name"],
            source["provider"],
            source["url"],
            source["filename"],
            source["format"],
            source.get("update_frequency"),
            source.get("license_note"),
            metadata.get("content_length"),
            metadata.get("last_modified"),
        ),
    )
    conn.commit()


def mark_source_imported(conn: sqlite3.Connection, source_key: str) -> None:
    conn.execute(
        "UPDATE source_registry SET imported_at = datetime('now') WHERE key = ?",
        (source_key,),
    )
    conn.commit()


def import_csv_reader(
    conn: sqlite3.Connection,
    reader: csv.DictReader,
    table_name: str,
    selected_columns: list[str] | None = None,
    row_limit: int | None = None,
) -> int:
    header = reader.fieldnames or []
    columns = selected_columns or header
    columns = [column for column in columns if column in header]
    if not columns:
        raise ValueError(f"No matching columns found for table {table_name}")

    conn.execute(f"DROP TABLE IF EXISTS {q(table_name)}")
    create_sql = ", ".join(f"{q(column)} TEXT" for column in columns)
    conn.execute(f"CREATE TABLE {q(table_name)} ({create_sql})")

    placeholders = ", ".join("?" for _ in columns)
    insert_sql = f"INSERT INTO {q(table_name)} ({', '.join(q(column) for column in columns)}) VALUES ({placeholders})"

    batch: list[tuple[str | None, ...]] = []
    imported = 0
    for row in reader:
        batch.append(tuple(row.get(column) for column in columns))
        if len(batch) >= SQLITE_BATCH_SIZE:
            conn.executemany(insert_sql, batch)
            imported += len(batch)
            batch.clear()
            if imported and imported % (SQLITE_BATCH_SIZE * 10) == 0:
                print(f"[import] {table_name}: {imported:,} rows")
        if row_limit and imported + len(batch) >= row_limit:
            remaining = row_limit - imported
            if remaining > 0:
                conn.executemany(insert_sql, batch[:remaining])
                imported += remaining
            batch.clear()
            break
    if batch:
        conn.executemany(insert_sql, batch)
        imported += len(batch)
    conn.commit()
    print(f"[import] {table_name}: {imported:,} rows total")
    return imported


def open_csv_from_zip(zip_path: Path, member_name: str) -> csv.DictReader:
    archive = zipfile.ZipFile(zip_path)
    file_handle = archive.open(member_name, "r")
    text_handle = io.TextIOWrapper(file_handle, encoding="utf-8-sig", newline="")
    return csv.DictReader(text_handle)


def list_csv_members(zip_path: Path) -> list[str]:
    with zipfile.ZipFile(zip_path) as archive:
        return sorted(name for name in archive.namelist() if name.lower().endswith(".csv"))


def import_usda_csv_package(conn: sqlite3.Connection, zip_path: Path) -> None:
    wanted_tables = {
        "food.csv": "usda_food",
        "food_nutrient.csv": "usda_food_nutrient",
        "nutrient.csv": "usda_nutrient",
        "food_category.csv": "usda_food_category",
        "measure_unit.csv": "usda_measure_unit",
        "food_portion.csv": "usda_food_portion",
        "branded_food.csv": "usda_branded_food",
        "survey_fndds_food.csv": "usda_survey_fndds_food",
        "sr_legacy_food.csv": "usda_sr_legacy_food",
        "foundation_food.csv": "usda_foundation_food",
        "input_food.csv": "usda_input_food",
        "wweia_food_category.csv": "usda_wweia_food_category",
    }

    members = list_csv_members(zip_path)
    member_lookup = {Path(name).name.lower(): name for name in members}

    for csv_name, table_name in wanted_tables.items():
        member = member_lookup.get(csv_name)
        if not member:
            print(f"[import] skip missing USDA member {csv_name}")
            continue
        print(f"[import] USDA {member} -> {table_name}")
        with zipfile.ZipFile(zip_path) as archive:
            with archive.open(member, "r") as file_handle:
                text_handle = io.TextIOWrapper(file_handle, encoding="utf-8-sig", newline="")
                reader = csv.DictReader(text_handle)
                import_csv_reader(conn, reader, table_name)

    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_usda_food_fdc_id ON usda_food("fdc_id");
        CREATE INDEX IF NOT EXISTS idx_usda_food_nutrient_fdc_id ON usda_food_nutrient("fdc_id");
        CREATE INDEX IF NOT EXISTS idx_usda_food_nutrient_nutrient_id ON usda_food_nutrient("nutrient_id");
        CREATE INDEX IF NOT EXISTS idx_usda_food_portion_fdc_id ON usda_food_portion("fdc_id");
        CREATE INDEX IF NOT EXISTS idx_usda_branded_food_fdc_id ON usda_branded_food("fdc_id");
        """
    )
    conn.commit()
    build_usda_summary(conn)


def load_nutrient_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM usda_nutrient").fetchall()
    conn.row_factory = None
    return rows


def row_get(row: sqlite3.Row, *keys: str) -> str | None:
    row_keys = set(row.keys())
    for key in keys:
        if key in row_keys:
            return row[key]
    return None


def resolve_usda_nutrient_ids(conn: sqlite3.Connection) -> dict[str, str]:
    wanted: dict[str, str] = {}
    scores: dict[str, int] = {}
    rows = load_nutrient_rows(conn)
    for row in rows:
        nutrient_id = str(row_get(row, "id") or "").strip()
        nutrient_id_lc = nutrient_id.lower()
        number = str(row_get(row, "nutrient_nbr", "number") or "").strip().lower()
        name = str(row_get(row, "name") or "").strip().lower()
        unit = str(row_get(row, "unit_name") or "").strip().lower()
        for output_name, matcher in USDA_INTERESTING_NUTRIENTS.items():
            score = 0
            if nutrient_id_lc in matcher.get("ids", set()):
                score = 4
            elif number in matcher.get("numbers", set()):
                score = 3
            elif name in matcher["names"] and unit in matcher.get("units", set()):
                score = 2
            elif name in matcher["names"]:
                score = 1
            if score > scores.get(output_name, 0):
                wanted[output_name] = nutrient_id
                scores[output_name] = score
    return wanted


def build_usda_summary(conn: sqlite3.Connection) -> None:
    nutrient_ids = resolve_usda_nutrient_ids(conn)
    if not nutrient_ids:
        raise RuntimeError("Could not resolve USDA nutrient ids")

    select_parts = [
        "f.\"fdc_id\" AS source_food_id",
        "'usda' AS source",
        "f.\"description\" AS name",
        "f.\"data_type\" AS data_type",
        "fc.\"description\" AS category",
        "bf.\"brand_owner\" AS brand_owner",
        "bf.\"brand_name\" AS brand_name",
        "bf.\"ingredients\" AS ingredients",
        "bf.\"serving_size\" AS serving_size",
        "bf.\"serving_size_unit\" AS serving_size_unit",
        "bf.\"household_serving_fulltext\" AS household_serving_fulltext",
        "bf.\"branded_food_category\" AS branded_food_category",
    ]
    for output_name, nutrient_id in nutrient_ids.items():
        select_parts.append(
            f"MAX(CASE WHEN fn.\"nutrient_id\" = '{nutrient_id}' THEN CAST(fn.\"amount\" AS REAL) END) AS {q(output_name)}"
        )

    conn.execute("DROP TABLE IF EXISTS usda_food_summary")
    sql = f"""
        CREATE TABLE usda_food_summary AS
        SELECT
            {", ".join(select_parts)}
        FROM usda_food f
        LEFT JOIN usda_food_category fc ON f."food_category_id" = fc."id"
        LEFT JOIN usda_branded_food bf ON f."fdc_id" = bf."fdc_id"
        LEFT JOIN usda_food_nutrient fn ON f."fdc_id" = fn."fdc_id"
        GROUP BY
            f."fdc_id",
            f."description",
            f."data_type",
            fc."description",
            bf."brand_owner",
            bf."brand_name",
            bf."ingredients",
            bf."serving_size",
            bf."serving_size_unit",
            bf."household_serving_fulltext",
            bf."branded_food_category"
    """
    conn.execute(sql)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usda_food_summary_name ON usda_food_summary(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usda_food_summary_source_food_id ON usda_food_summary(source_food_id)")

    conn.execute("DROP TABLE IF EXISTS usda_food_portion_enriched")
    conn.execute(
        """
        CREATE TABLE usda_food_portion_enriched AS
        SELECT
            fp."id" AS portion_id,
            fp."fdc_id" AS source_food_id,
            fp."amount" AS amount,
            mu."name" AS measure_unit,
            fp."modifier" AS modifier,
            fp."portion_description" AS portion_description,
            fp."gram_weight" AS gram_weight,
            fp."seq_num" AS sequence_number
        FROM usda_food_portion fp
        LEFT JOIN usda_measure_unit mu ON fp."measure_unit_id" = mu."id"
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usda_food_portion_enriched_source_food_id ON usda_food_portion_enriched(source_food_id)")
    conn.commit()


def import_open_food_facts_csv(conn: sqlite3.Connection, gz_path: Path, row_limit: int | None) -> None:
    with gzip.open(gz_path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        import_csv_reader(conn, reader, "off_products_raw", selected_columns=OFF_SELECTED_COLUMNS, row_limit=row_limit)

    conn.executescript(
        """
        DROP TABLE IF EXISTS off_food_summary;
        CREATE TABLE off_food_summary AS
        SELECT
            code AS source_food_id,
            'open_food_facts' AS source,
            product_name AS name,
            generic_name AS generic_name,
            brands AS brand_name,
            COALESCE(main_category_en, main_category, categories) AS category,
            serving_size AS serving_size,
            quantity AS package_quantity,
            ingredients_text AS ingredients,
            countries AS countries,
            nutrition_grades AS nutrition_grade,
            nova_group AS nova_group,
            ecoscore_grade AS ecoscore_grade,
            CAST("energy-kcal_100g" AS REAL) AS energy_kcal_100g,
            CAST(fat_100g AS REAL) AS fat_g_100g,
            CAST("saturated-fat_100g" AS REAL) AS saturated_fat_g_100g,
            CAST(carbohydrates_100g AS REAL) AS carb_g_100g,
            CAST(sugars_100g AS REAL) AS sugar_g_100g,
            CAST(fiber_100g AS REAL) AS fiber_g_100g,
            CAST(proteins_100g AS REAL) AS protein_g_100g,
            CASE
                WHEN sodium_100g IS NOT NULL AND sodium_100g != '' THEN CAST(sodium_100g AS REAL) * 1000
                WHEN salt_100g IS NOT NULL AND salt_100g != '' THEN CAST(salt_100g AS REAL) * 393.4
                ELSE NULL
            END AS sodium_mg_100g,
            image_url AS image_url
        FROM off_products_raw
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_off_food_summary_name ON off_food_summary(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_off_food_summary_source_food_id ON off_food_summary(source_food_id)")
    conn.commit()


def build_unified_catalog(conn: sqlite3.Connection) -> None:
    union_parts: list[str] = []
    if table_exists(conn, "usda_food_summary"):
        union_parts.append(
            """
            SELECT
                source,
                source_food_id,
                name,
                COALESCE(brand_name, brand_owner) AS brand,
                category,
                data_type,
                energy_kcal_100g,
                protein_g_100g,
                fat_g_100g,
                saturated_fat_g_100g,
                carb_g_100g,
                sugar_g_100g,
                fiber_g_100g,
                sodium_mg_100g,
                serving_size,
                serving_size_unit,
                household_serving_fulltext,
                ingredients
            FROM usda_food_summary
            """
        )
    if table_exists(conn, "off_food_summary"):
        union_parts.append(
            """
            SELECT
                source,
                source_food_id,
                name,
                brand_name AS brand,
                category,
                'branded_product' AS data_type,
                energy_kcal_100g,
                protein_g_100g,
                fat_g_100g,
                saturated_fat_g_100g,
                carb_g_100g,
                sugar_g_100g,
                fiber_g_100g,
                sodium_mg_100g,
                serving_size,
                NULL AS serving_size_unit,
                NULL AS household_serving_fulltext,
                ingredients
            FROM off_food_summary
            WHERE name IS NOT NULL AND TRIM(name) != ''
            """
        )

    conn.execute("DROP TABLE IF EXISTS food_catalog")
    if not union_parts:
        conn.execute(
            """
            CREATE TABLE food_catalog (
                source TEXT,
                source_food_id TEXT,
                name TEXT,
                brand TEXT,
                category TEXT,
                data_type TEXT,
                energy_kcal_100g REAL,
                protein_g_100g REAL,
                fat_g_100g REAL,
                saturated_fat_g_100g REAL,
                carb_g_100g REAL,
                sugar_g_100g REAL,
                fiber_g_100g REAL,
                sodium_mg_100g REAL,
                serving_size TEXT,
                serving_size_unit TEXT,
                household_serving_fulltext TEXT,
                ingredients TEXT
            )
            """
        )
    else:
        conn.execute("CREATE TABLE food_catalog AS " + " UNION ALL ".join(union_parts))

    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_food_catalog_source ON food_catalog(source);
        CREATE INDEX IF NOT EXISTS idx_food_catalog_name ON food_catalog(name);
        """
    )

    if table_exists(conn, "food_catalog_fts"):
        conn.execute("DROP TABLE food_catalog_fts")
    conn.execute(
        """
        CREATE VIRTUAL TABLE food_catalog_fts USING fts5(
            source_food_id,
            name,
            brand,
            category,
            ingredients,
            content='food_catalog',
            content_rowid='rowid'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO food_catalog_fts(rowid, source_food_id, name, brand, category, ingredients)
        SELECT rowid, source_food_id, name, brand, category, ingredients
        FROM food_catalog
        """
    )
    conn.commit()


def query_table_count(conn: sqlite3.Connection, table_name: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {q(table_name)}").fetchone()[0])


def write_stats(conn: sqlite3.Connection, destination: Path) -> dict:
    tables = [
        "usda_food",
        "usda_food_nutrient",
        "usda_food_summary",
        "usda_food_portion_enriched",
        "off_products_raw",
        "off_food_summary",
        "food_catalog",
    ]
    stats = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tables": {}}
    for table_name in tables:
        if table_exists(conn, table_name):
            stats["tables"][table_name] = query_table_count(conn, table_name)

    if table_exists(conn, "source_registry"):
        rows = conn.execute(
            "SELECT key, name, provider, filename, downloaded_at, imported_at, content_length, last_modified FROM source_registry ORDER BY key"
        ).fetchall()
        stats["sources"] = [
            {
                "key": row[0],
                "name": row[1],
                "provider": row[2],
                "filename": row[3],
                "downloaded_at": row[4],
                "imported_at": row[5],
                "content_length": row[6],
                "last_modified": row[7],
            }
            for row in rows
        ]

    destination.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def parse_sources_argument(values: list[str] | None) -> list[str]:
    return values if values else list(DEFAULT_SOURCES)


def iter_download_targets(selected_keys: Iterable[str], source_map: dict[str, dict]) -> list[dict]:
    targets = []
    for key in selected_keys:
        if key not in source_map:
            raise SystemExit(f"Unknown source key: {key}")
        targets.append(source_map[key])
    return targets


def run_download(args: argparse.Namespace) -> None:
    ensure_directories()
    source_map = load_sources()
    selected_keys = parse_sources_argument(args.sources)
    if not selected_keys:
        raise SystemExit("No sources selected. Pass --sources explicitly. USDA is no longer the default.")
    selected = iter_download_targets(selected_keys, source_map)
    conn = create_connection(args.db_path)
    create_metadata_tables(conn)
    try:
        for source in selected:
            metadata = head_metadata(source["url"])
            path = RAW_DIR / source["filename"]
            download_file(source["url"], path, force=args.force)
            register_source_download(conn, source, metadata)
    finally:
        conn.close()


def run_build(args: argparse.Namespace) -> None:
    ensure_directories()
    source_map = load_sources()
    selected_keys = parse_sources_argument(args.sources)
    if not selected_keys:
        raise SystemExit("No sources selected. Pass --sources explicitly. USDA is no longer the default.")
    selected = iter_download_targets(selected_keys, source_map)

    conn = create_connection(args.db_path)
    create_metadata_tables(conn)
    try:
        if args.download:
            for source in selected:
                metadata = head_metadata(source["url"])
                download_file(source["url"], RAW_DIR / source["filename"], force=args.force)
                register_source_download(conn, source, metadata)

        if "usda_full_csv" in selected_keys:
            usda = source_map["usda_full_csv"]
            zip_path = RAW_DIR / usda["filename"]
            if not zip_path.exists():
                raise SystemExit(f"Missing source file: {zip_path}")
            import_usda_csv_package(conn, zip_path)
            mark_source_imported(conn, usda["key"])

        if "open_food_facts_csv" in selected_keys:
            off = source_map["open_food_facts_csv"]
            gz_path = RAW_DIR / off["filename"]
            if not gz_path.exists():
                raise SystemExit(f"Missing source file: {gz_path}")
            import_open_food_facts_csv(conn, gz_path, row_limit=args.off_max_rows)
            mark_source_imported(conn, off["key"])

        build_unified_catalog(conn)
        stats = write_stats(conn, args.stats_path)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    finally:
        conn.close()


def run_stats(args: argparse.Namespace) -> None:
    conn = create_connection(args.db_path)
    try:
        stats = write_stats(conn, args.stats_path)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a local nutrition database from open datasets.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download_parser = subparsers.add_parser("download", help="Download source archives only.")
    download_parser.add_argument("--sources", nargs="+", help="Source keys to download.")
    download_parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    download_parser.add_argument("--force", action="store_true", help="Redownload existing files.")
    download_parser.set_defaults(func=run_download)

    build_parser_cmd = subparsers.add_parser("build", help="Download, import, and build the SQLite database.")
    build_parser_cmd.add_argument("--sources", nargs="+", help="Source keys to build.")
    build_parser_cmd.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    build_parser_cmd.add_argument("--stats-path", type=Path, default=DEFAULT_STATS_PATH)
    build_parser_cmd.add_argument("--download", action="store_true", help="Download source archives before import.")
    build_parser_cmd.add_argument("--force", action="store_true", help="Redownload existing source archives.")
    build_parser_cmd.add_argument(
        "--off-max-rows",
        type=int,
        default=None,
        help="Optional row cap for Open Food Facts import. Useful for first-pass builds.",
    )
    build_parser_cmd.set_defaults(func=run_build)

    stats_parser = subparsers.add_parser("stats", help="Write and print stats for an existing database.")
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
