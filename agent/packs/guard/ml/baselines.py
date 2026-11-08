"""Per-user baselines for ml/: personas.json + legit history jsonl, loaded once.

The brain's store does not seed data/history/*.jsonl, so ml/ reads it here. Training and serving
both go through this module, so features see the same baselines (train == serve).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def personas() -> dict:
    try:
        return json.loads((DATA / "personas.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def baseline(user_id: str) -> dict:
    return personas().get("baselines", {}).get(user_id, {}) or {}


@lru_cache(maxsize=16)
def legit_history(user_id: str) -> tuple[dict, ...]:
    path = DATA / "history" / f"{user_id}.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ()
    return tuple(json.loads(line) for line in lines if line.strip())
