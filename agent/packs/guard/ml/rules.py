"""Rules score from events only (no Store). Port of agent/core/toolbox.py rules_score.

Same weights and reason texts as the brain's rules so swapping this in never moves a live verdict.
Also the floor the trained model may not go below (D-010).

Pre-freeze hardening (D-053a, from an adversarial probe of synthetic cases; 0 dev-set verdict changes):
the login that stands for "her device / her region" is the last SUCCESSFUL one in the past hour; a SIM swap
is judged by the device it moves the line to; a call that just ended still counts;
a remote swap to a never-seen device is a medium takeover even with no region clue; a burst from her own
known device in her usual area is not a bot. Each change is mirrored for Lane 1 to port into toolbox.py.
"""
from __future__ import annotations

from datetime import datetime

from . import baselines

SENSITIVE = ("transfer_pin.requested", "otp.sent", "sim_swap.requested")
CALL_GRACE_S = 15 * 60      # a scammer who hangs up and lets her "finish" is still the call context
LOGIN_WINDOW_S = 3600       # how far back a successful sign-in can stand for the actor's device/region


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


def active_call(events: list[dict], t: datetime | None = None) -> dict | None:
    """The call that is the context for time t: the last call.started that has not ended, or ended less than
    CALL_GRACE_S before t. A never-ended call stays the context however old it is: the demo replays a fixture
    call.started hours before the live trigger, so an age cap would break the demo path (known limit: a
    days-old dropped call record still reads as live; core/store.py active_call behaves the same)."""
    ended = {e.get("call_id"): ts(e) for e in events if e["type"] == "call.ended"}
    starts = [e for e in events if e["type"] == "call.started"]
    if t is None:
        starts = [e for e in starts if e.get("call_id") not in ended]
        return starts[-1] if starts else None
    live = []
    for e in starts:
        end = ended.get(e.get("call_id"))
        if end is not None and (t - end).total_seconds() > CALL_GRACE_S:
            continue
        live.append(e)
    return live[-1] if live else None


def facts(user_id: str, event: dict, history: list[dict]) -> dict:
    """Everything the rules (and later the features) read, from events + baselines only."""
    ev = upto(event, history)
    t = ts(event)
    base = baselines.baseline(user_id)
    call = active_call(ev, t)
    cd = (call or {}).get("data", {})
    suspicious = bool(call) and not cd.get("seen_before", False) and (cd.get("attestation") != "A" or cd.get("scam_label", False))
    minutes = int((t - ts(call)).total_seconds() // 60) if call else 0
    call_ended = bool(call) and any(e["type"] == "call.ended" and e.get("call_id") == call.get("call_id") for e in ev)
    during = [e for e in ev if call and e.get("call_id") == call.get("call_id") and e["type"] not in ("call.started", "call.ended")]
    off_during = any(e["type"] == "protection.changed" and e["data"].get("enabled") is False for e in during)

    logins = [e for e in ev if e["type"] == "login"]
    known = set(base.get("known_device_hashes") or [])
    ed = event.get("data") or {}
    swap_target = ed.get("new_device_hash") if event["type"] == "sim_swap.requested" else None
    ok = [e for e in logins if e["data"].get("succeeded") is not False and (t - ts(e)).total_seconds() <= LOGIN_WINDOW_S]
    last_login = ok[-1] if ok else (logins[-1] if logins else None)
    if swap_target:
        # A SIM swap is judged by the device it moves the line to: if that device signed in recently, its login
        # is the actor's (the owner's later login must not mask the attacker's). A target that never signed in
        # (e.g. an eSIM set up from an attacker's laptop session, fixture T1) falls back to the session's login.
        mine = [e for e in logins if e["data"].get("device_hash") == swap_target and (t - ts(e)).total_seconds() <= 600]
        if mine:
            last_login = mine[-1]
    ld = (last_login or {}).get("data", {})
    new_device = bool(last_login) and (ld.get("new_device", False) or (bool(known) and ld.get("device_hash") not in known))
    if swap_target and known and swap_target not in known:
        new_device = True
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
    remote_swap = event["type"] == "sim_swap.requested" and ed.get("channel") != "store"
    return {
        "events": ev, "call": call, "call_ended": call_ended, "caller_name": cd.get("caller_name"), "suspicious": suspicious,
        "minutes": minutes, "off_during_call": off_during, "new_device": new_device, "region_match": region_match,
        "login_region": login_region, "line_region": where, "prior_transfer_pins": prior_pins, "portal": portal,
        "remote_swap": remote_swap,
    }


def _bot(ev: list[dict], event: dict) -> tuple[int, int, int]:
    """Failed sign-ins, distinct sign-in regions and failed PIN attempts in the 10 minutes up to the trigger."""
    t = ts(event)
    recent = [e for e in ev if 0 <= (t - ts(e)).total_seconds() <= 600]
    logins = [e for e in recent if e["type"] == "login"]
    failed = sum(1 for e in logins if e["data"].get("succeeded") is False)
    regions = len({e["data"].get("region") for e in logins if e["data"].get("region")})
    pin_failures = sum(1 for e in recent if e["type"] == "pin.attempt" and e["data"].get("ok") is False)
    return failed, regions, pin_failures


def score(user_id: str, event: dict, history: list[dict]) -> dict:
    f = facts(user_id, event, history)
    reasons: list[dict] = []

    def add(feature: str, w: float, text: str) -> None:
        reasons.append({"feature": feature, "contribution": w, "text": text})

    def takeover_reasons() -> None:
        add("new_device", 0.35, "A device never seen on this account")
        add("region_mismatch", 0.35, f"Request from {f['login_region']} while her line is in {f['line_region']}")

    failed, regions, pin_failures = _bot(f["events"], event)
    burst = failed >= 3 or regions >= 3 or pin_failures >= 3 or failed + pin_failures >= 3
    stranger = f["new_device"] or f["region_match"] is False or regions >= 2 or pin_failures >= 3
    if burst and f["new_device"] and f["region_match"] is False and event["type"] in SENSITIVE:
        # The burst got in and is now moving the line: that is a takeover with a burst behind it, not "a bot".
        takeover_reasons()
        if pin_failures:
            add("pin_guess_burst", 0.2, f"{pin_failures} wrong PIN attempts within 10 minutes")
        if failed:
            add("failed_login_burst", 0.2, f"{failed} failed sign-ins from {regions} regions within 10 minutes")
        p, threat = 0.9, "takeover"
    elif burst and stranger:
        # An automated burst also looks like "new device, wrong region", so check it first. A PIN-guessing
        # burst followed by one failed login is a bot too (dev-set family pin_guess_burst, D-053a).
        if pin_failures >= 3:
            add("pin_guess_burst", 0.4, f"{pin_failures} wrong PIN attempts within 10 minutes")
        if failed >= 3 or regions >= 3:
            add("failed_login_burst", 0.4, f"{failed} failed sign-ins from {regions} regions within 10 minutes")
        if not reasons:
            add("failed_login_burst", 0.4, f"{failed} failed sign-ins and {pin_failures} wrong PINs within 10 minutes")
        p, threat = 0.85, "bot"
    elif f["new_device"] and f["region_match"] is False:
        takeover_reasons()
        p, threat = 0.9, "takeover"
    elif f["remote_swap"] and f["new_device"]:
        # No region clue, but the line is being moved remotely to a device this account has never used.
        add("new_device", 0.35, "A device never seen on this account")
        add("remote_sim_swap", 0.25, "SIM moved to it remotely, not in a store with ID")
        p, threat = 0.6, "takeover"
    else:
        p, threat = 0.1, "legit"
        if burst:  # her own known device, her usual area: a forgotten password, not an attack
            p = 0.3
            add("failed_login_burst", 0.2, f"{failed + pin_failures} failed attempts from her own device in her usual area")
        if f["suspicious"]:
            p += 0.25
            call_text = (f"On a {f['minutes']}-minute call from an unverified number that never contacted her" if not f["call_ended"]
                         else "A call from an unverified number that never contacted her ended minutes ago")
            add("unverified_call", 0.25, call_text)
            if f["off_during_call"]:
                p += 0.3
                add("protection_off_during_call", 0.3, "A protection was turned off during that call")
            if event["type"] in SENSITIVE:
                p += 0.2
                add("sensitive_action_during_call", 0.2, "Transfer PIN, login code or SIM change requested during that call")
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
