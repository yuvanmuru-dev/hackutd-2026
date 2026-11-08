"""Lane 2b risk model. The brain calls score() from agent/core/toolbox.py and the Risk agent.

score(user_id, event, history) -> RiskScore   (< 100 ms, no network)
score_text(text) -> RiskScore                 (threat "scam_text" or "legit")

Errors are NOT swallowed here: if anything raises, toolbox.score falls back to the brain's own rules,
which is the safe failure. Returning "legit" on an internal error would be the unsafe one.
"""
from __future__ import annotations

from . import rules
from .text import score_text

__all__ = ["score", "score_text"]


def score(user_id: str, event: dict, history: list[dict]) -> dict:
    if event["type"] == "message.forwarded":
        return score_text((event.get("data") or {}).get("text", ""))
    return rules.score(user_id, event, history)
