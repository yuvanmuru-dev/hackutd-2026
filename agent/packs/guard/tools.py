"""Read-only Context agent tools for the synthetic guard pack.

The brain owns protection state and actions. These functions take a snapshot of
its records and the generated account history, then return sourced summaries.
"""
from __future__ import annotations

import copy
import json
import os
import re
from collections import Counter
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

from packs.guard.external import check_message, policy_lookup

HISTORY_DIR = Path(__file__).parent / "data" / "history"
PERSONAS_PATH = Path(__file__).parent / "data" / "personas.json"
UNVERIFIED = {"B", "C", "none"}


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _lock(store):
    return getattr(store, "lock", nullcontext())


def _history_events(user_id: str) -> list[dict]:
    if not re.fullmatch(r"usr_[a-z0-9_]+", user_id):
        return []
    path = HISTORY_DIR / f"{user_id}.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _baseline(user_id: str) -> dict:
    if not PERSONAS_PATH.exists():
        return {}
    data = json.loads(PERSONAS_PATH.read_text(encoding="utf-8"))
    return data.get("baselines", {}).get(user_id, {})


def _events(store, user_id: str, days: int | None = None) -> list[dict]:
    # A live event takes precedence when a seeded event has the same ID.
    events = {event["event_id"]: event for event in _history_events(user_id)}
    with _lock(store):
        live = [copy.deepcopy(event) for event in store.events.values() if event["user_id"] == user_id]
    events.update((event["event_id"], event) for event in live)
    selected = sorted(events.values(), key=lambda event: _parse(event["ts"]))
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(days))
        selected = [event for event in selected if _parse(event["ts"]) >= cutoff]
    return selected


def _answer(summary: str, result, name: str, record: str | None = None) -> dict:
    source = {"name": name}
    if record:
        source["record"] = record
    return {"summary": summary.replace("\n", " "), "result": result, "source": source}


def _active_call(store, user_id: str) -> dict | None:
    with _lock(store):
        return copy.deepcopy(store.active_call(user_id))


def account_history(store, user_id: str, days: int = 90, **_) -> dict:
    events = _events(store, user_id, days)
    logins = [event for event in events if event["type"] == "login" and event["data"].get("succeeded")]
    pins = [event for event in events if event["type"] == "transfer_pin.requested"]
    baseline = _baseline(user_id)
    historical_logins = [event for event in _history_events(user_id) if event["type"] == "login"
                         and event["data"].get("succeeded")]
    region_counts = Counter(event["data"].get("region") for event in historical_logins)
    usual_regions = baseline.get("usual_login_regions") or [
        region for region, _ in region_counts.most_common(3) if region
    ]
    baseline_devices = baseline.get("known_device_hashes")
    known_device_count = (len(baseline_devices) if baseline_devices is not None
                          else len({event["data"]["device_hash"] for event in historical_logins}))
    current_is_pin = bool(events and events[-1]["type"] == "transfer_pin.requested")
    result = {
        "days": days,
        "logins": len(logins),
        "known_device_count": known_device_count,
        "usual_regions": usual_regions,
        "home_region": usual_regions[0] if usual_regions else None,
        "login_region_pattern": baseline.get("login_region_pattern"),
        "usual_login_hour_bucket": baseline.get("usual_login_hour_bucket"),
        "login_frequency_bucket": baseline.get("login_frequency_bucket"),
        "account_changes_90d": baseline.get("account_changes_90d"),
        "usual_care_channel": baseline.get("usual_care_channel"),
        "care_contacts_90d": baseline.get("care_contacts_90d"),
        "transfer_pins_before": max(0, len(pins) - int(current_is_pin)),
    }
    summary = (f"{result['transfer_pins_before']} prior transfer PIN request(s) in {days} days"
               f" · {result['known_device_count']} known device(s)")
    record = (f"history/{user_id}.jsonl" if (HISTORY_DIR / f"{user_id}.jsonl").exists()
              else f"users/{user_id}/timeline")
    return _answer(summary, result, "Synthetic account history", record)


def device_sim_status(store, user_id: str, **_) -> dict:
    events = _events(store, user_id, 90)
    logins = [event for event in events if event["type"] == "login"]
    swaps = [event for event in events if event["type"] == "sim_swap.requested"]
    baseline = _baseline(user_id)
    last = logins[-1] if logins else None
    known_devices = baseline.get("known_device_hashes")
    result = {
        "last_login_new_device": bool(last and last["data"].get("new_device")),
        "sim_swap_requests": len(swaps),
        "known_device_count": (len(known_devices) if known_devices is not None
                               else len({event["data"].get("device_hash") for event in logins})),
        "last_login_device_known": (last["data"].get("device_hash") in known_devices
                                    if last and known_devices is not None else None),
        "device_age_bucket": baseline.get("device_age_bucket"),
        "sim_age_bucket": baseline.get("sim_age_bucket"),
        "sim_changes_90d": baseline.get("sim_changes_90d"),
    }
    summary = ("Last sign-in used a new device" if result["last_login_new_device"]
               else "Last sign-in used a known device" if last else "No sign-in recorded")
    summary += f" · {len(swaps)} SIM swap request(s) in 90 days"
    record = f"events/{last['event_id']}" if last else f"history/{user_id}.jsonl"
    return _answer(summary, result, "Synthetic device and SIM records", record)


def protection_status(store, user_id: str, **_) -> dict:
    # Store.protection_state() expires holds as a side effect, so read fields
    # directly. The brain remains the sole owner of transitions.
    with _lock(store):
        protections = copy.deepcopy(store.protections[user_id])
        transfer_pin = copy.deepcopy(store.transfer_pins[user_id])
        call = copy.deepcopy(store.active_call(user_id))
    if (transfer_pin.get("status") == "held" and transfer_pin.get("hold_until")
            and _parse(transfer_pin["hold_until"]) < datetime.now(timezone.utc)):
        transfer_pin = {"status": "active", "hold_until": None}
    suspicious = bool(call and not call["seen_before"]
                      and (call["attestation"] in UNVERIFIED or call["scam_label"]))
    state = {
        "user_id": user_id,
        "protections": list(protections.values()),
        "shield_mode": suspicious,
        "transfer_pin": transfer_pin,
    }
    changes = [
        {
            "name": event["data"]["name"],
            "enabled": event["data"]["enabled"],
            "ts": event["ts"],
            "during_call": bool(event.get("call_id")),
            "event_id": event["event_id"],
        }
        for event in _events(store, user_id, 90)
        if event["type"] == "protection.changed"
    ][-5:]
    off_during_call = [change["name"] for change in changes if not change["enabled"]
                       and change["during_call"]]
    result = {"state": state, "recent_changes": changes, "off_during_call": off_during_call}
    summary = ("Turned off during a call: " + ", ".join(name.replace("_", " ") for name in off_during_call)
               if off_during_call else "No protection turned off during a call")
    return _answer(summary, result, "Protection log", f"protections/{user_id}")


def call_context(store, user_id: str, **_) -> dict:
    call = _active_call(store, user_id)
    if not call:
        return _answer("No active call", {"active": False}, "Call record")
    started = _parse(call["started_at"])
    call_events = [event for event in _events(store, user_id)
                   if event.get("call_id") == call["call_id"]
                   and event["type"] not in {"call.started", "call.ended"}]
    if os.getenv("MOCK") == "1":
        triggers = [event for event in call_events
                    if event["type"] in {"transfer_pin.requested", "otp.sent"}]
        last_event = max(triggers or call_events, key=lambda event: event["ts"], default=None)
        end = _parse(last_event["ts"]) if last_event else started
    else:
        end = datetime.now(timezone.utc)
    minutes = max(0, int((end - started).total_seconds() // 60))
    during = [event["type"] for event in call_events]
    verified = call["attestation"] == "A"
    suspicious = not call["seen_before"] and (not verified or call["scam_label"])
    result = {
        "active": True,
        "minutes": minutes,
        "caller_name": call.get("caller_name"),
        "attestation": call["attestation"],
        "verified": verified,
        "seen_before": call["seen_before"],
        "scam_label": call["scam_label"],
        "suspicious": suspicious,
        "actions_during_call": during,
    }
    summary = (f"Active call for {minutes} min · {'verified' if verified else 'unverified'}"
               f" · {'seen before' if call['seen_before'] else 'number unseen'}")
    if call.get("caller_name"):
        summary += f" · caller ID {call['caller_name']}"
    return _answer(summary, result, "Call record (simulated carrier signal)", f"calls/{call['call_id']}")


def location_match(store, user_id: str, event_id: str | None = None, **_) -> dict:
    events = _events(store, user_id)
    target = next((event for event in events if event["event_id"] == event_id), None) if event_id else None
    if event_id and target is None:
        return _answer("Line location unknown (unverifiable)",
                       {"request_region": None, "line_region": None, "match": None},
                       "Login region vs line serving region (simulated carrier signal)")
    as_of = _parse(target["ts"]) if target else None
    eligible = [event for event in events if as_of is None or _parse(event["ts"]) <= as_of]
    logins = [event for event in eligible if event["type"] == "login"]
    lines = [event for event in eligible if event["type"] == "line.region"]
    login = logins[-1] if logins else None
    line = lines[-1] if lines else None
    region = login["data"].get("region") if login else None
    line_region = line["data"].get("region") if line else None
    result = {"request_region": region, "line_region": line_region,
              "match": region == line_region if region and line_region else None}
    source_name = "Login region vs line serving region (simulated carrier signal)"
    if result["match"] is None:
        return _answer("Line location unknown (unverifiable)", result, source_name,
                       f"events/{line['event_id']}" if line else None)
    summary = (f"Request from {region} · phone is in {line_region}"
               f" · {'match' if result['match'] else 'MISMATCH'}")
    return _answer(summary, result, source_name, f"events/{line['event_id']}")


def portal_signals(store, user_id: str, session_id: str | None = None, **_) -> dict:
    events = [event for event in _events(store, user_id) if event["type"] == "portal.signals"
              and (session_id is None or event["data"].get("session_id") == session_id)]
    if not events:
        return _answer("No portal behavior recorded", None, "Portal behavior (derived)")
    event = events[-1]
    data = copy.deepcopy(event["data"])
    summary = (f"{round(data['hesitation_ms'] / 1000)} s hesitation"
               f" · {data['tab_switches']} tab switch(es)"
               f" · paste into PIN: {'yes' if data['paste_into_pin'] else 'no'}")
    # Typing rhythm vs her on-device baseline (timing only, D-006). Evidence for agents and dashboards;
    # risk scoring (rules_score, frozen ML pack D-053) never reads it.
    rhythm = data.get("typing_rhythm_distance")
    if isinstance(rhythm, (int, float)) and not isinstance(rhythm, bool) and rhythm >= 0:
        summary += " · typing matches her usual rhythm" if rhythm < 1 else f" · typing rhythm {rhythm:.1f}× off her usual"
    return _answer(summary, data, "Portal behavior (derived numbers)", f"events/{event['event_id']}")


def recent_scam_reports(store, number_hash: str | None = None, domain: str | None = None, **_) -> dict:
    # An applied report_number action is a recorded report. A risk label alone
    # is never treated as a confirmed report.
    with _lock(store):
        cases = copy.deepcopy(list(store.cases.values()))
        calls = copy.deepcopy(store.calls)
        call_events = copy.deepcopy([event for event in store.events.values()
                                     if event["type"] == "call.started"])
        registry = copy.deepcopy(getattr(store, "scam_numbers", {}))
    reports = []
    seen = set()
    if not domain:
        for item_hash, details in registry.items():
            if number_hash is None or item_hash == number_hash:
                reports.append({"number_hash": item_hash, "record": f"scam_numbers/{item_hash}",
                                "report_count": details.get("report_count", 1)})
                seen.add(item_hash)
        hashes_by_call = {event.get("call_id"): event["data"].get("other_number_hash")
                          for event in call_events}
        for case in cases:
            call = calls.get(case.get("call_id")) if case.get("call_id") else None
            item_hash = (call.get("other_number_hash") if call else None) or hashes_by_call.get(case.get("call_id"))
            if not item_hash or item_hash in seen or (number_hash is not None and item_hash != number_hash):
                continue
            for action in case.get("actions", []):
                if action.get("kind") == "report_number" and action.get("status") == "applied":
                    reports.append({"number_hash": item_hash, "case_id": case["case_id"],
                                    "record": f"actions/{action['action_id']}"})
                    seen.add(item_hash)
    summary = f"{len(reports)} recorded scam report(s)" if not domain else "No domain report registry available"
    return _answer(summary, reports, "Scam report records", "scam_numbers")


TOOLS = {
    "account_history": account_history,
    "device_sim_status": device_sim_status,
    "protection_status": protection_status,
    "call_context": call_context,
    "location_match": location_match,
    "portal_signals": portal_signals,
    "check_message": check_message,
    "recent_scam_reports": recent_scam_reports,
    "policy_lookup": policy_lookup,
}


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": required, "additionalProperties": False},
        },
    }


_USER = {"type": "string", "description": "Synthetic user ID, for example usr_maya"}
TOOL_SCHEMAS = [
    _schema("account_history", "Summarize the user's recent synthetic account activity.",
            {"user_id": _USER, "days": {"type": "integer", "minimum": 1, "maximum": 365}}, ["user_id"]),
    _schema("device_sim_status", "Check recent sign-in device and SIM swap request signals.",
            {"user_id": _USER}, ["user_id"]),
    _schema("protection_status", "Read current protections, transfer PIN hold, and recent changes.",
            {"user_id": _USER}, ["user_id"]),
    _schema("call_context", "Read minimal active-call metadata and actions during that call.",
            {"user_id": _USER}, ["user_id"]),
    _schema("location_match", "Compare request and line regions when both are available.",
            {"user_id": _USER, "event_id": {"type": "string"}}, ["user_id"]),
    _schema("portal_signals", "Read derived portal behavior for the latest or selected session.",
            {"user_id": _USER, "session_id": {"type": "string"}}, ["user_id"]),
    _schema("check_message", "Check a customer-forwarded text for suspicious domains and links.",
            {"text": {"type": "string", "maxLength": 4096}}, ["text"]),
    _schema("recent_scam_reports", "Find confirmed reports for a hashed number or domain.",
            {"number_hash": {"type": "string"}, "domain": {"type": "string"}}, []),
    _schema("policy_lookup", "Retrieve short carrier safety policy guidance with sources.",
            {"question": {"type": "string"}}, ["question"]),
]
