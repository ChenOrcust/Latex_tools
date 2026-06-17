from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from latex_formula_tool.runtime_paths import bundled_pandoc_dir


PANDOC_VERSION = "3.8.2.1"
PANDOC_ZIP_URL = (
    f"https://github.com/jgm/pandoc/releases/download/{PANDOC_VERSION}/"
    f"pandoc-{PANDOC_VERSION}-windows-x86_64.zip"
)


def main() -> int:
    target_dir = bundled_pandoc_dir()
    target_exe = target_dir / "pandoc.exe"
    if target_exe.exists():
        print(f"Pandoc already installed: {target_exe}")
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="pandoc_install_"))
    zip_path = temp_root / "pandoc.zip"
    extract_dir = temp_root / "extract"
    try:
        print(f"Downloading Pandoc {PANDOC_VERSION}...")
        with urlopen(PANDOC_ZIP_URL) as response, zip_path.open("wb") as handle:
            shutil.copyfileobj(response, handle)

        print("Extracting Pandoc...")
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)

        candidates = list(extract_dir.rglob("pandoc.exe"))
        if not candidates:
            print("Pandoc executable not found in archive.", file=sys.stderr)
            return 1

        source_exe = candidates[0]
        shutil.copy2(source_exe, target_exe)
        print(f"Pandoc installed: {target_exe}")
        return 0
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
