from __future__ import annotations

import importlib
import importlib.metadata
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from latex_formula_tool.env_profile_store import EnvProfileStore


REQUIRED_PACKAGES = [
    ("PyQt6", "PyQt6.QtCore"),
    ("PyQt6-WebEngine", "PyQt6.QtWebEngineWidgets"),
    ("Pillow", "PIL"),
    ("openai", "openai"),
    ("python-dotenv", "dotenv"),
    ("markdown", "markdown"),
]


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def main() -> int:
    print(f"Python: {sys.version.split()[0]}")
    print(f"Executable: {sys.executable}")
    print()

    ok = True
    for package_name, import_name in REQUIRED_PACKAGES:
        version = package_version(package_name)
        try:
            importlib.import_module(import_name)
            status = "OK"
        except Exception as exc:
            ok = False
            status = f"FAIL ({exc})"
        print(f"{package_name:14} {version:12} {status}")

    print()
    env_store = EnvProfileStore(PROJECT_ROOT / ".env")
    loaded = env_store.load_profiles()
    if loaded.has_managed_profiles:
        active = next(
            (profile for profile in loaded.profiles if profile.profile_name == loaded.active_profile_name),
            loaded.profiles[0],
        )
        key_status = "set" if active.api_key else "missing"
        print(f"Active Profile: {active.profile_name}")
        print(f"LLM_API_KEY: {key_status}")
        print(f"LLM_MODEL: {active.model or '(empty)'}")
        print(f"LLM_BASE_URL: {active.base_url or '(empty)'}")
    else:
        key_status = "set" if (os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY")) else "missing"
        print("Active Profile: not configured in .env")
        print(f"LLM_API_KEY: {key_status}")
        print(f"LLM_MODEL: {os.getenv('LLM_MODEL', os.getenv('QWEN_VL_MODEL', 'qwen3-vl-plus'))}")
        print(
            "LLM_BASE_URL: "
            f"{os.getenv('LLM_BASE_URL', os.getenv('QWEN_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1'))}"
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
