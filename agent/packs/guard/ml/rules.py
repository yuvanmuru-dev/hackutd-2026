"""Rules score from events only (no Store). Port of agent/core/toolbox.py rules_score.

Same weights and reason texts as the brain's rules so swapping this in never moves a live verdict.
Also the floor the trained model may not go below (D-010).
"""
from __future__ import annotations

from datetime import datetime

from . import baselines

SENSITIVE = ("transfer_pin.requested", "otp.sent")


def conf(p: float) -> str:
    return "high" if p >= 0.8 else "medium" if p >= 0.5 else "low"


def ts(e: dict) -> datetime:
    return datetime.fromisoformat(e["ts"].replace("Z", "+00:00"))


def upto(event: dict, history: list[dict]) -> list[dict]:
    """History as of the trigger (inclusive), sorted, with the trigger present exactly once."""
    t = ts(event)
    seen, out = set(), []
    for e in sorted([*history, event], key=ts):
        if e["event_id"] in seen or ts(e) > t:
            continue
        seen.add(e["event_id"])
        out.append(e)
    return out


def active_call(events: list[dict]) -> dict | None:
    """Last call.started without a later call.ended for the same call_id."""
    ended = {e.get("call_id") for e in events if e["type"] == "call.ended"}
    starts = [e for e in events if e["type"] == "call.started" and e.get("call_id") not in ended]
    return starts[-1] if starts else None


def facts(user_id: str, event: dict, history: list[dict]) -> dict:
    """Everything the rules (and later the features) read, from events + baselines only."""
    ev = upto(event, history)
    base = baselines.baseline(user_id)
    call = active_call(ev)
    cd = (call or {}).get("data", {})
    suspicious = bool(call) and not cd.get("seen_before", False) and (cd.get("attestation") != "A" or cd.get("scam_label", False))
    minutes = int((ts(event) - ts(call)).total_seconds() // 60) if call else 0
    during = [e for e in ev if call and e.get("call_id") == call.get("call_id") and e["type"] not in ("call.started", "call.ended")]
    off_during = any(e["type"] == "protection.changed" and e["data"].get("enabled") is False for e in during)

    logins = [e for e in ev if e["type"] == "login"]
    last_login = logins[-1] if logins else None
    known = set(base.get("known_device_hashes") or [])
    ld = (last_login or {}).get("data", {})
    new_device = bool(last_login) and (ld.get("new_device", False) or (bool(known) and ld.get("device_hash") not in known))
    lines = [e for e in ev if e["type"] == "line.region"]
    line_region = lines[-1]["data"].get("region") if lines else None
    login_region = ld.get("region")
    if login_region and line_region:
        region_match: bool | None = login_region == line_region
        where = line_region
    elif login_region and base.get("usual_login_regions"):
        region_match = login_region in base["usual_login_regions"]
        where = base["usual_login_regions"][0]
    else:
        region_match, where = None, None

    prior_pins = sum(1 for e in ev if e["type"] == "transfer_pin.requested" and e["event_id"] != event["event_id"])
    prior_pins += sum(1 for e in baselines.legit_history(user_id) if e.get("type") == "transfer_pin.requested")
    portal = next((e["data"] for e in reversed(ev) if e["type"] == "portal.signals"), {}) or {}
    return {
        "events": ev, "call": call, "caller_name": cd.get("caller_name"), "suspicious": suspicious, "minutes": minutes,
        "off_during_call": off_during, "new_device": new_device, "region_match": region_match,
        "login_region": login_region, "line_region": where, "prior_transfer_pins": prior_pins, "portal": portal,
    }


def _bot(ev: list[dict], event: dict) -> tuple[int, int]:
    t = ts(event)
    window = [e for e in ev if e["type"] == "login" and 0 <= (t - ts(e)).total_seconds() <= 600]
    failed = sum(1 for e in window if e["data"].get("succeeded") is False)
    regions = len({e["data"].get("region") for e in window if e["data"].get("region")})
    return failed, regions


def score(user_id: str, event: dict, history: list[dict]) -> dict:
    f = facts(user_id, event, history)
    reasons: list[dict] = []

    def add(feature: str, w: float, text: str) -> None:
        reasons.append({"feature": feature, "contribution": w, "text": text})

    failed, regions = _bot(f["events"], event)
    if failed >= 3 or regions >= 3:  # an automated burst also looks like "new device, wrong region": check it first
        add("failed_login_burst", 0.4, f"{failed} failed sign-ins from {regions} regions within 10 minutes")
        p, threat = 0.85, "bot"
    elif f["new_device"] and f["region_match"] is False:
        add("new_device", 0.35, "A device never seen on this account")
        add("region_mismatch", 0.35, f"Request from {f['login_region']} while her line is in {f['line_region']}")
        p, threat = 0.9, "takeover"
    else:
        p, threat = 0.1, "legit"
        if f["suspicious"]:
            p += 0.25
            add("unverified_call", 0.25, f"On a {f['minutes']}-minute call from an unverified number that never contacted her")
            if f["off_during_call"]:
                p += 0.3
                add("protection_off_during_call", 0.3, "A protection was turned off during that call")
            if event["type"] in SENSITIVE:
                p += 0.2
                add("sensitive_action_during_call", 0.2, "Transfer PIN or login code requested during that call")
            if f["prior_transfer_pins"] == 0 and event["type"] == "transfer_pin.requested":
                p += 0.05
                add("first_time_action", 0.05, "First transfer PIN request on record")
            pt = f["portal"]
            if (pt.get("tab_switches") or 0) >= 2 or (pt.get("hesitation_ms") or 0) > 20000:
                p += 0.05
                add("portal_hesitation", 0.05, "Long pauses and leaving the page mid-flow")
            if not f["new_device"] and f["region_match"] is not False:
                add("known_device_home_region", -0.05, "Her own device and area: it is really her")
            threat = "coached" if p >= 0.5 else "legit"
        p = min(p, 0.95)
    reasons.sort(key=lambda r: -abs(r["contribution"]))
    return {"threat": threat, "probability": round(p, 2), "calibrated": False, "confidence": conf(p), "anomaly": None,
            "top_reasons": reasons[:5] or [{"feature": "none", "contribution": 0, "text": "Nothing unusual"}], "model": "rules"}
