from __future__ import annotations

from pathlib import Path
import shutil
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = REPO_ROOT / "nutrition_app" / "static"
PUBLIC_ROOT = REPO_ROOT / "public"
PUBLIC_STATIC_ROOT = PUBLIC_ROOT / "static"
BUNDLED_DB_PATH = REPO_ROOT / "nutrition_app" / "data" / "china_nutrition.db"


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> int:
    if not STATIC_ROOT.exists():
        print(f"Static source not found: {STATIC_ROOT}", file=sys.stderr)
        return 1

    if PUBLIC_ROOT.exists():
        shutil.rmtree(PUBLIC_ROOT)
    PUBLIC_STATIC_ROOT.mkdir(parents=True, exist_ok=True)

    copy_file(STATIC_ROOT / "index.html", PUBLIC_ROOT / "index.html")
    copy_file(STATIC_ROOT / "app.js", PUBLIC_STATIC_ROOT / "app.js")
    copy_file(STATIC_ROOT / "styles.css", PUBLIC_STATIC_ROOT / "styles.css")
    copy_file(STATIC_ROOT / "favicon.svg", PUBLIC_STATIC_ROOT / "favicon.svg")

    if not BUNDLED_DB_PATH.exists():
        print(
            "Bundled database not found. Run `python scripts/stage_vercel_db.py` first.",
            file=sys.stderr,
        )
        return 1

    print("Prepared Vercel public bundle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
