"""Lane 2b risk model. The brain calls score() from agent/core/toolbox.py and the Risk agent.

score(user_id, event, history) -> RiskScore   (< 100 ms, no network)
score_text(text) -> RiskScore                 (threat "scam_text" or "legit")

When models/risk.json exists: XGBoost (pure-Python walk) + isotonic calibration + path-attribution
reasons, with the rules as a floor the model cannot undercut (D-010) -> model "ml+rules".
Without it: the rules alone -> model "rules".

Errors are NOT swallowed here: if anything raises, toolbox.score falls back to the brain's own rules,
which is the safe failure. Returning "legit" on an internal error would be the unsafe one.
"""
from __future__ import annotations

from . import infer, rules
from .features import AGAINST_TEXT, FEATURE_ORDER, build, reason_text
from .text import score_text

__all__ = ["score", "score_text"]

THREATS = ("coached", "takeover", "bot")
NOT_A_REASON = {"region_unknown", "logins_10m"}  # true but uninformative on their own
# Features whose ABSENCE (value 0) is the reassuring fact, and the ones whose PRESENCE is.
REASSURING_WHEN_ZERO = {"new_device", "region_mismatch", "call_unverified", "odd_hour_for_user"}
REASSURING_WHEN_SET = {"caller_seen_before", "sim_swap_in_store"}


def _reassuring(i: int, x: list[float]) -> bool:
    f = FEATURE_ORDER[i]
    return (f in REASSURING_WHEN_ZERO and x[i] == 0) or (f in REASSURING_WHEN_SET and x[i] > 0)


def _reasons(threat: str, x: list[float], c: list[float], ctx: dict) -> list[dict]:
    total = sum(abs(v) for v in c) or 1.0
    order = sorted(range(len(c)), key=lambda i: -c[i])
    out: list[dict] = []
    for i in order:  # features that pushed TOWARD the predicted class and are true for this case
        f = FEATURE_ORDER[i]
        if c[i] <= 0.01 or len(out) == 3 or f in NOT_A_REASON or f.startswith("trigger_"):
            continue
        if threat == "legit":
            if not _reassuring(i, x):
                continue
            text = AGAINST_TEXT.get(f) or reason_text(f, ctx)
        else:
            if x[i] <= 0 or f in REASSURING_WHEN_SET:
                continue
            text = reason_text(f, ctx)
        out.append({"feature": f, "contribution": round(c[i] / total, 2), "text": text})
    if threat != "legit":  # one honest "against it" line, as the fixtures show
        for i in sorted(range(len(c)), key=lambda i: c[i]):
            if c[i] < -0.01 and _reassuring(i, x):
                out.append({"feature": FEATURE_ORDER[i], "contribution": round(c[i] / total, 2),
                            "text": AGAINST_TEXT.get(FEATURE_ORDER[i], reason_text(FEATURE_ORDER[i], ctx))})
                break
    return out or [{"feature": "none", "contribution": 0, "text": "Nothing unusual"}]


def score(user_id: str, event: dict, history: list[dict]) -> dict:
    if event["type"] == "message.forwarded":
        return score_text((event.get("data") or {}).get("text", ""))
    floor = rules.score(user_id, event, history)
    x, ctx = build(user_id, event, history)
    pred = infer.predict(x)
    if pred is None:  # no trained model shipped: rules only
        return floor
    probs, contrib, model, cal = pred
    k = max(range(len(probs)), key=lambda i: probs[i])
    threat = model["classes"][k]
    p, calibrated = infer.calibrate(probs[k], cal)
    reasons = _reasons(threat, x, contrib[k], ctx)

    # A threat call that is more likely wrong than right (calibrated p < 0.5) doesn't fire on its own:
    # if the rules see nothing either, say "looks legitimate" with the matching (low) confidence.
    if threat in THREATS and calibrated and p < 0.5 and floor["threat"] == "legit":
        li = model["classes"].index("legit")
        threat, p, calibrated = "legit", 1.0 - p, False
        reasons = _reasons("legit", x, contrib[li], ctx)

    # Rules floor (D-010): the model can't talk itself out of an obvious case.
    if floor["threat"] in THREATS and floor["probability"] >= 0.5:
        if threat != floor["threat"]:
            threat, p, calibrated, reasons = floor["threat"], floor["probability"], False, floor["top_reasons"]
        elif floor["probability"] > p:
            p, calibrated = floor["probability"], False
    p = round(min(max(p, 0.0), 0.99), 2)
    return {"threat": threat, "probability": p, "calibrated": calibrated, "confidence": rules.conf(p),
            "anomaly": None, "top_reasons": reasons[:4], "model": "ml+rules"}
