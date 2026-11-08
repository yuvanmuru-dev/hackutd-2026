"""score_text: scam vs legit for a forwarded message.

Rules path (always available, offline): T-Mobile lookalike domains + pressure language, using the
store-free helpers in packs/guard/external.py (synthetic registry, no network). The embedding model
(M4) plugs in here later with a 2 s timeout and falls back to these rules on any error.
"""
from __future__ import annotations

from ..external import URGENT_RE, _extract, _lookalike
from .rules import conf


def score_text(text: str) -> dict:
    text = text or ""
    hosts = [h for h, _ in _extract(text)]
    lookalikes = [h for h in hosts if _lookalike(h)]
    urgent = bool(URGENT_RE.search(text))
    p = 0.9 if lookalikes else 0.6 if urgent else 0.2
    reasons = []
    if lookalikes:
        reasons.append({"feature": "lookalike_domain", "contribution": 0.5, "text": f"{lookalikes[0]} imitates T-Mobile"})
    if urgent:
        reasons.append({"feature": "urgent_language", "contribution": 0.2, "text": "Pressure language (locked, verify now)"})
    return {"threat": "scam_text" if p >= 0.5 else "legit", "probability": p, "calibrated": False, "confidence": conf(p),
            "anomaly": None, "top_reasons": reasons or [{"feature": "none", "contribution": 0, "text": "Nothing suspicious found"}],
            "model": "rules"}
