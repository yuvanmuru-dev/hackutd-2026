"""Feature vector for the risk classifier. Built only from (event, history, baselines), so training
(scenario events up to the trigger) and serving (the brain's store events) compute the same thing.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import baselines
from .rules import SENSITIVE, facts, ts

TRIGGERS = ("sim_swap.requested", "transfer_pin.requested", "otp.sent", "login", "pin.attempt", "protection.changed")

FEATURE_ORDER = [
    # Call features are gated on the call being unverified: a call from a verified or known number is not
    # a risk in itself (revised after held-out review; see models/meta.json "feature_revisions").
    "call_unverified", "unverified_call_minutes", "caller_claims_carrier", "caller_seen_before",
    "protection_off_during_call", "sensitive_action_during_call", "first_time_action", "actions_during_unverified_call",
    "sim_swap_in_store",
    "new_device", "region_mismatch", "region_unknown", "odd_hour_for_user",
    "failed_logins_10m", "distinct_regions_10m", "pin_failures_10m", "logins_10m",
    "hesitation_s", "tab_switches", "paste_into_pin",
    *[f"trigger_{t.split('.')[0]}" for t in TRIGGERS],
]

# Plain-English reason per feature, in the tone of contracts/fixtures/risk.t*.json.
# {x} placeholders are filled from the facts at prediction time.
REASON_TEXT = {
    "call_unverified": "On a call from a number that couldn't be verified and never contacted her",
    "unverified_call_minutes": "{minutes} minutes into that call",
    "caller_claims_carrier": "Caller ID claims to be T-Mobile",
    "caller_seen_before": "The caller is someone she has talked to before",
    "protection_off_during_call": "A protection was turned off during that call",
    "sensitive_action_during_call": "Transfer PIN or login code requested during that call",
    "first_time_action": "First transfer PIN request on record",
    "actions_during_unverified_call": "Account changes made during that call",
    "sim_swap_in_store": "SIM change done in a store with ID",
    "new_device": "A device never seen on this account",
    "region_mismatch": "Request from {login_region} while her line is in {line_region}",
    "region_unknown": "Where her phone is right now is unknown",
    "odd_hour_for_user": "An hour she doesn't usually sign in",
    "failed_logins_10m": "{failed} failed sign-ins within 10 minutes",
    "distinct_regions_10m": "Sign-ins from {regions} different places within 10 minutes",
    "pin_failures_10m": "{pin_failures} wrong PIN attempts within 10 minutes",
    "logins_10m": "Many sign-ins in a few minutes",
    "hesitation_s": "Long pauses on the security pages",
    "tab_switches": "Left the page {tab_switches} times mid-flow",
    "paste_into_pin": "A PIN was pasted in, not typed",
    "trigger_sim_swap": "A SIM swap was requested",
    "trigger_transfer_pin": "A transfer PIN was requested",
    "trigger_otp": "A login code was sent",
    "trigger_login": "A sign-in",
    "trigger_pin": "A PIN attempt",
    "trigger_protection": "A protection setting changed",
}
# When a feature pushes AWAY from the predicted threat, say why in its own words.
AGAINST_TEXT = {
    "new_device": "Her own device: it is really her",
    "region_mismatch": "Her usual area: it is really her",
    "call_unverified": "The caller is verified or known to her",
    "caller_seen_before": "The caller is someone she has talked to before",
    "odd_hour_for_user": "Her usual time of day",
    "sim_swap_in_store": "SIM change done in a store with ID",
}

HOUR_BUCKETS = {  # local hours (America/Chicago) that count as usual
    "daytime": range(8, 19),
    "afternoon_evening": range(12, 24),
    "overnight_02_05": range(1, 7),
    "daytime_evening": range(8, 24),
}


def _local_hour(t: datetime) -> int:
    # America/Chicago without tzdata (Windows has none): CDT (UTC-5) from 2nd Sun of March to 1st Sun of November.
    y = t.year
    mar = datetime(y, 3, 8, tzinfo=t.tzinfo) + timedelta(days=(6 - datetime(y, 3, 8).weekday()) % 7)
    nov = datetime(y, 11, 1, tzinfo=t.tzinfo) + timedelta(days=(6 - datetime(y, 11, 1).weekday()) % 7)
    off = -5 if mar <= t < nov else -6
    return (t + timedelta(hours=off)).hour


def _window(ev: list[dict], t: datetime, kind: str) -> list[dict]:
    return [e for e in ev if e["type"] == kind and 0 <= (t - ts(e)).total_seconds() <= 600]


def build(user_id: str, event: dict, history: list[dict]) -> tuple[list[float], dict]:
    """Returns (vector in FEATURE_ORDER, facts used to fill reason texts)."""
    f = facts(user_id, event, history)
    ev, t, call = f["events"], ts(event), f["call"]
    cd = (call or {}).get("data", {})
    logins = _window(ev, t, "login")
    failed = sum(1 for e in logins if e["data"].get("succeeded") is False)
    regions = len({e["data"].get("region") for e in logins if e["data"].get("region")})
    pin_fail = sum(1 for e in _window(ev, t, "pin.attempt") if e["data"].get("ok") is False)
    during = [e for e in ev if call and e.get("call_id") == call.get("call_id") and e["type"] not in ("call.started", "call.ended")]
    bucket = baselines.baseline(user_id).get("usual_login_hour_bucket")
    odd = bucket in HOUR_BUCKETS and _local_hour(t) not in HOUR_BUCKETS[bucket]
    pt = f["portal"]
    vals = {
        "call_unverified": float(f["suspicious"]),
        "unverified_call_minutes": float(f["minutes"] if f["suspicious"] else 0),
        "caller_claims_carrier": float("t-mobile" in (cd.get("caller_name") or "").lower()),
        "caller_seen_before": float(bool(cd.get("seen_before"))),
        "protection_off_during_call": float(f["off_during_call"]),
        "sensitive_action_during_call": float(f["suspicious"] and event["type"] in SENSITIVE),
        "first_time_action": float(event["type"] == "transfer_pin.requested" and f["prior_transfer_pins"] == 0),
        "actions_during_unverified_call": float(len(during) if f["suspicious"] else 0),
        "sim_swap_in_store": float(event["type"] == "sim_swap.requested" and (event.get("data") or {}).get("channel") == "store"),
        "new_device": float(f["new_device"]),
        "region_mismatch": float(f["region_match"] is False),
        "region_unknown": float(f["region_match"] is None),
        "odd_hour_for_user": float(odd),
        "failed_logins_10m": float(failed),
        "distinct_regions_10m": float(regions),
        "pin_failures_10m": float(pin_fail),
        "logins_10m": float(len(logins)),
        "hesitation_s": float((pt.get("hesitation_ms") or 0) / 1000),
        "tab_switches": float(pt.get("tab_switches") or 0),
        "paste_into_pin": float(bool(pt.get("paste_into_pin"))),
        **{f"trigger_{k.split('.')[0]}": float(event["type"] == k) for k in TRIGGERS},
    }
    ctx = {**f, "failed": failed, "regions": regions, "pin_failures": pin_fail,
           "tab_switches": int(pt.get("tab_switches") or 0)}
    return [vals[k] for k in FEATURE_ORDER], ctx


def reason_text(feature: str, ctx: dict, against: bool = False) -> str:
    template = (AGAINST_TEXT if against else REASON_TEXT).get(feature) or REASON_TEXT.get(feature) or feature.replace("_", " ")
    try:
        return template.format(**{k: ctx.get(k) for k in ("minutes", "login_region", "line_region", "failed", "regions",
                                                           "pin_failures", "tab_switches")})
    except (KeyError, IndexError):
        return template
