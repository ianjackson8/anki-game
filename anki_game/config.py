"""Optional local config, mainly so someone else cloning this repo can point
it at wherever their Anki collection actually lives."""

from __future__ import annotations

import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.toml"


def configured_collection_path() -> Path | None:
    """Path from config.toml's `anki_collection_path`, if the file exists
    and sets one. Returns None to fall back to auto-detection."""
    if not CONFIG_PATH.exists():
        return None
    with CONFIG_PATH.open("rb") as f:
        data = tomllib.load(f)
    raw = data.get("anki_collection_path")
    return Path(raw).expanduser() if raw else None
