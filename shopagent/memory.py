"""Simple long-term shopper profile stored as JSON."""

from __future__ import annotations

import json
from pathlib import Path

MEMORY_PATH = Path(__file__).resolve().parent.parent / "data" / "shopper_memory.json"

_EMPTY_PROFILE = {
    "name": None,
    "preferred_size": None,
    "preferred_color": None,
    "preferred_category": None,
    "notes": None,
}

_PROFILE_KEYS = tuple(_EMPTY_PROFILE.keys())


def load_memory() -> dict:
    if not MEMORY_PATH.exists():
        return dict(_EMPTY_PROFILE)

    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(_EMPTY_PROFILE)

    if not isinstance(data, dict):
        return dict(_EMPTY_PROFILE)

    profile = dict(_EMPTY_PROFILE)
    for key in _PROFILE_KEYS:
        value = data.get(key)
        if value:
            profile[key] = value
    return profile


def save_memory(**updates) -> dict:
    profile = load_memory()
    for key in _PROFILE_KEYS:
        if key in updates and updates[key] is not None:
            value = updates[key]
            profile[key] = value.strip() if isinstance(value, str) else value
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    return profile
