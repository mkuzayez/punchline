"""YAML config loader with defaults."""

from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_config(name: str = "settings") -> dict[str, Any]:
    """Load a YAML config file from the config directory."""
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def get(key: str, default: Any = None) -> Any:
    """Get a dotted config key like 'reddit.subreddits'."""
    cfg = load_config()
    parts = key.split(".")
    current = cfg
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return default
        if current is None:
            return default
    return current
