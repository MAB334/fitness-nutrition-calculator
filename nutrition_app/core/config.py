from dataclasses import dataclass
from pathlib import Path
import os


APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXTERNAL_DB_PATH = Path(r"E:\爬虫抓包数据\china\processed\china_nutrition.db")
BUNDLED_DB_PATH = APP_ROOT / "data" / "china_nutrition.db"


def resolve_default_db_path() -> Path:
    explicit_path = os.environ.get("CHINA_NUTRITION_DB_PATH")
    if explicit_path:
        return Path(explicit_path)
    if BUNDLED_DB_PATH.exists():
        return BUNDLED_DB_PATH
    return DEFAULT_EXTERNAL_DB_PATH


DEFAULT_DB_PATH = resolve_default_db_path()


@dataclass(frozen=True)
class Settings:
    db_path: Path
    host: str
    port: int
    static_dir: Path


def load_settings() -> Settings:
    host = os.environ.get("NUTRITION_APP_HOST", "127.0.0.1")
    port = int(os.environ.get("NUTRITION_APP_PORT", "8010"))
    return Settings(
        db_path=DEFAULT_DB_PATH,
        host=host,
        port=port,
        static_dir=APP_ROOT / "static",
    )
