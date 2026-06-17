from __future__ import annotations

import shutil
import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def env_path() -> Path:
    return app_root() / ".env"


def env_example_path() -> Path:
    return app_root() / ".env.example"


def docs_dir() -> Path:
    return app_root() / "docs"


def outputs_dir() -> Path:
    path = app_root() / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def venv_dir() -> Path:
    return app_root() / ".venv"


def bundled_pandoc_dir() -> Path:
    return venv_dir() / "tools" / "pandoc"


def ensure_local_env() -> None:
    target = env_path()
    if target.exists():
        return

    example = env_example_path()
    if example.exists():
        shutil.copyfile(example, target)

