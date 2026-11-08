"""score_text: scam vs legit for a forwarded message.

Rules path (always available, offline), policy D-052 set before any results: pressure wording alone is not a
scam. scam_text needs a lookalike T-Mobile domain, a request for a code/PIN/password or money (gift cards,
wire, crypto...), or a link to a non-official domain together with pressure. Urgency alone, or a plain link
alone, is low: "worth a look". Uses the store-free helpers in packs/guard/external.py (no network).
An embedding model can plug in here later with a 2 s timeout and rules fallback; it needs a TRAINABLE benign
set first (the #56 benign texts are evaluation-only, D-052).

Pre-freeze hardening (D-053a) from an adversarial probe with invented texts: a carrier's own "don't share
this code" is not a request for the code; a payment receipt that mentions a rail is not a request for money;
a few more ask verbs (provide, tell, what is, have ready) and the word OTP; simple obfuscation (c0de, "P I N")
is normalised for matching only; T-Mobile's own domains are not lookalikes; transposed "tmoblie" is.
"""
from __future__ import annotations

import re

from ..external import RESERVED_TLDS, URGENT_RE, _extract, _lookalike
from .rules import conf

_WB = "\\b"
_NOUN = "(code|pin|passcode|password|otp)"
_ASK_VERB = ("(reply|send|share|text (?:me|us|back|it|them|this|that|your)|give|forward|provide|tell|read|have|"
             "what(?:'s| is| are))")
# A message that asks her to send back a code or PIN. T-Mobile never asks for one by text (D-012), so this
# alone marks a scam even with no link (added after held-out review: variant code_request_no_link).
CREDENTIAL_ASK = re.compile(_WB + _ASK_VERB + _WB + ".{0,60}?" + _WB + _NOUN + _WB, re.IGNORECASE)
# "Don't share this code", "we will never ask for your PIN": the carrier's own warning, not an ask.
_NEGATED_ASK = re.compile(
    r"\b(?:don'?t|do not|never|won'?t|will not|not)\s+(?:ever\s+)?(?:share|send|give|reply|text|forward|tell|ask|provide)"
    r"|\bnever\s+asks?\s+(?:you\s+)?(?:for|to)\b", re.IGNORECASE)
# A gate/garage/Wi-Fi code from family is a physical code, not an account credential.
_PHYSICAL = re.compile(r"\b(?:gate|garage|door|wi-?fi|parking|building|keypad|locker|lockbox|alarm)\s+" + _NOUN + _WB, re.IGNORECASE)
# A request to PAY through rails scammers use (D-052). A receipt or alert that merely mentions the rail is not one.
MONEY_ASK = re.compile(
    r"\b(?:buy|pay|purchase|send|load|put|transfer)\b\W*(?:\w+\W+){0,4}?"
    r"\b(gift ?cards?|wire|bit ?coin|crypto(?:currency)?|zelle|venmo|cash ?app|western union|moneygram|prepaid (?:debit )?card)\b"
    r"|\bwire\s+(?:the money|\$?\d)", re.IGNORECASE)
OFFICIAL = ("t-mobile.com", "tmobile.com", "t-mobiletuesdays.com", "metrobyt-mobile.com")  # Lane 1 confirms the list
_TRANSPOSED = {"tmobile"[:i] + "tmobile"[i + 1] + "tmobile"[i] + "tmobile"[i + 2:] for i in range(len("tmobile") - 1)}
_LEET = str.maketrans("01345@$", "oieasas")
_SPACED = re.compile(r"\b(?:[A-Za-z][ .]){2,}[A-Za-z]\b")


def _official(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in OFFICIAL)


def _unresolvable(host: str) -> bool:  # reserved names (RFC 2606/6761) can't point anywhere
    return host.rsplit(".", 1)[-1] in RESERVED_TLDS


def _lookalike_host(host: str) -> bool:
    if _official(host):
        return False
    if _lookalike(host):
        return True
    norm = host.replace("-", "").translate(_LEET)
    return any(t in norm for t in _TRANSPOSED)


def _normalise(text: str) -> str:
    """Matching-only copy: 'P I N' -> 'PIN', 'c0de' -> 'code'. Never shown; URLs are left to _extract on the original."""
    out = _SPACED.sub(lambda m: re.sub(r"[ .]", "", m.group()), text)
    def deleet(m: re.Match) -> str:
        tok = m.group()
        if "://" in tok or "." in tok.strip(".,") or sum(c.isalpha() for c in tok) < 2 or not re.search(r"[01345@$]", tok):
            return tok
        return tok.translate(_LEET)
    return re.sub(r"\S+", deleet, out)


def _asks_for_code(norm: str) -> bool:
    for m in CREDENTIAL_ASK.finditer(norm):
        before = norm[max(0, m.start() - 30):m.start()]
        if _NEGATED_ASK.search(before + norm[m.start():m.start(1) + len(m.group(1))]):
            continue
        noun_start = m.start(len(m.groups()))
        if _PHYSICAL.search(norm[max(0, noun_start - 12):m.end()]):
            continue
        return True
    return False


def score_text(text: str) -> dict:
    text = text or ""
    norm = _normalise(text)
    hosts = [h for h, _ in _extract(text)]
    lookalikes = [h for h in hosts if _lookalike_host(h)]
    links = [h for h in hosts if not _official(h) and not _unresolvable(h) and h not in lookalikes]
    urgent = bool(URGENT_RE.search(norm))
    asks = _asks_for_code(norm)
    money = bool(MONEY_ASK.search(norm))
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
