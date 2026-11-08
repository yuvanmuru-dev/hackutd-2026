"""score_text: scam vs legit for a forwarded message.

Rules path (always available, offline), policy D-052 set before any results: pressure wording alone is not a
scam. scam_text needs a lookalike T-Mobile domain, a request for a code/PIN/password or money (gift cards,
wire, crypto...), or a link to a non-official domain together with pressure. Urgency alone, or a plain link
alone, is low: "worth a look". Uses the store-free helpers in packs/guard/external.py (no network).
An embedding model can plug in here later with a 2 s timeout and rules fallback; it needs a TRAINABLE benign
set first (the #56 benign texts are evaluation-only, D-052).
"""
from __future__ import annotations

import re

from ..external import RESERVED_TLDS, URGENT_RE, _extract, _lookalike
from .rules import conf

# A message that asks her to send back a code or PIN. T-Mobile never asks for one by text (D-012), so this
# alone marks a scam even with no link (added after held-out review: variant code_request_no_link).
_WB = "\\b"
CREDENTIAL_ASK = re.compile(
    _WB + "(reply|send|share|text|give|forward)" + _WB + ".{0,60}?" + _WB + "(code|pin|passcode|password)" + _WB,
    re.IGNORECASE,
)
# A request for money through rails scammers use (D-052). Generic "pay your bill" is not on this list.
MONEY_ASK = re.compile(
    _WB + "(gift ?cards?|wire (transfer|the money)|bitcoin|crypto(currency)?|zelle|venmo|cash ?app|"
    "western union|moneygram|prepaid (debit )?card)" + _WB,
    re.IGNORECASE,
)


def _official(host: str) -> bool:
    return host == "t-mobile.com" or host.endswith(".t-mobile.com")


def _unresolvable(host: str) -> bool:  # reserved names (RFC 2606/6761) can't point anywhere
    return host.rsplit(".", 1)[-1] in RESERVED_TLDS


def score_text(text: str) -> dict:
    text = text or ""
    hosts = [h for h, _ in _extract(text)]
    lookalikes = [h for h in hosts if _lookalike(h)]
    links = [h for h in hosts if not _official(h) and not _unresolvable(h) and h not in lookalikes]
    urgent = bool(URGENT_RE.search(text))
    asks = bool(CREDENTIAL_ASK.search(text))
    money = bool(MONEY_ASK.search(text))
    if lookalikes:
        p = 0.9
    elif asks or money:
        p = 0.85
    elif links and urgent:
        p = 0.75
    elif links or urgent:
        p = 0.35  # one weak signal: worth a look, not a scam (D-052)
    else:
        p = 0.1
    reasons = []
    if lookalikes:
        reasons.append({"feature": "lookalike_domain", "contribution": 0.5, "text": f"{lookalikes[0]} imitates T-Mobile"})
    if asks:
        reasons.append({"feature": "asks_for_code", "contribution": 0.45, "text": "Asks her to send a code or PIN (T-Mobile never does)"})
    if money:
        reasons.append({"feature": "asks_for_money", "contribution": 0.45, "text": "Asks for payment by gift card, wire or crypto"})
    if links:
        reasons.append({"feature": "unofficial_link", "contribution": 0.25, "text": f"Links to {links[0]}, not a T-Mobile site"})
    if urgent:
        reasons.append({"feature": "urgent_language", "contribution": 0.2,
                        "text": "Pressure language (locked, verify now)" if p >= 0.5
                        else "Pressure language, but no link or request: worth a look"})
    return {"threat": "scam_text" if p >= 0.5 else "legit", "probability": p, "calibrated": False, "confidence": conf(p),
            "anomaly": None, "top_reasons": reasons or [{"feature": "none", "contribution": 0, "text": "Nothing suspicious found"}],
            "model": "rules"}
