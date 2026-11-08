"""score_text: scam vs legit for a forwarded message.

Rules path (always available, offline): T-Mobile lookalike domains, a request to send back a code or
PIN, and pressure language, using the store-free helpers in packs/guard/external.py (synthetic registry,
no network). An embedding model can plug in here later with a 2 s timeout and fall back to these rules
on any error; it needs legit example texts first (the dataset has none).
"""
from __future__ import annotations

import re

from ..external import URGENT_RE, _extract, _lookalike
from .rules import conf

# A message that asks her to send back a code or PIN. T-Mobile never asks for one by text (D-012), so this
# alone marks a scam even with no link (added after held-out review: variant code_request_no_link).
_WB = "\\b"
CREDENTIAL_ASK = re.compile(
    _WB + "(reply|send|share|text|give|forward)" + _WB + ".{0,60}?" + _WB + "(code|pin|passcode|password)" + _WB,
    re.IGNORECASE,
)


def score_text(text: str) -> dict:
    text = text or ""
    hosts = [h for h, _ in _extract(text)]
    lookalikes = [h for h in hosts if _lookalike(h)]
    urgent = bool(URGENT_RE.search(text))
    asks = bool(CREDENTIAL_ASK.search(text))
    p = 0.9 if lookalikes else 0.85 if asks else 0.6 if urgent else 0.2
    reasons = []
    if lookalikes:
        reasons.append({"feature": "lookalike_domain", "contribution": 0.5, "text": f"{lookalikes[0]} imitates T-Mobile"})
    if asks:
        reasons.append({"feature": "asks_for_code", "contribution": 0.45, "text": "Asks her to send a code or PIN (T-Mobile never does)"})
    if urgent:
        reasons.append({"feature": "urgent_language", "contribution": 0.2, "text": "Pressure language (locked, verify now)"})
    return {"threat": "scam_text" if p >= 0.5 else "legit", "probability": p, "calibrated": False, "confidence": conf(p),
            "anomaly": None, "top_reasons": reasons or [{"feature": "none", "contribution": 0, "text": "Nothing suspicious found"}],
            "model": "rules"}
