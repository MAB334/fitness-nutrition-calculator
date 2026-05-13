from __future__ import annotations

import sys
from pathlib import Path
import shutil

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from nutrition_app.core.config import DEFAULT_EXTERNAL_DB_PATH

TARGET_DB = REPO_ROOT / "nutrition_app" / "data" / "china_nutrition.db"


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXTERNAL_DB_PATH
    if not source.exists():
        print(f"Source database not found: {source}", file=sys.stderr)
        return 1
    TARGET_DB.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, TARGET_DB)
    print(TARGET_DB)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
