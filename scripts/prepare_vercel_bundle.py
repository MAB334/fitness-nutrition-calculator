from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = REPO_ROOT / "nutrition_app" / "static"
PUBLIC_ROOT = REPO_ROOT / "public"
CATALOG_BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_static_catalog.py"


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def main() -> int:
    if not STATIC_ROOT.exists():
        print(f"Static source not found: {STATIC_ROOT}", file=sys.stderr)
        return 1

    subprocess.run([sys.executable, str(CATALOG_BUILD_SCRIPT)], cwd=REPO_ROOT, check=True)

    if PUBLIC_ROOT.exists():
        shutil.rmtree(PUBLIC_ROOT)
    (PUBLIC_ROOT / "static").mkdir(parents=True, exist_ok=True)

    copy_file(STATIC_ROOT / "index.html", PUBLIC_ROOT / "index.html")
    for path in STATIC_ROOT.rglob("*"):
        if not path.is_file() or path.name == "index.html":
            continue
        relative = path.relative_to(STATIC_ROOT)
        copy_file(path, PUBLIC_ROOT / "static" / relative)

    print("Prepared Vercel public bundle.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
