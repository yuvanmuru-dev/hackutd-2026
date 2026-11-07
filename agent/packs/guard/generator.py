"""Seeded synthetic guard scenarios and sparse account history.

Run from agent/: python3 -m packs.guard.generator
Check committed output without writing: python3 -m packs.guard.generator --check

Writes generated_*.json and five history/*.jsonl files. Hand-authored seed
scenarios are validated but never rewritten. History contains only normal
account events; line.region appears only in independent trigger scenarios.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from core.contracts import errors

SCENARIO_DIR = Path(__file__).resolve().parent / "data" / "scenarios"
DATA_DIR = SCENARIO_DIR.parent
HISTORY_DIR = DATA_DIR / "history"
HISTORY_START = datetime(2026, 8, 9, tzinfo=ZoneInfo("America/Chicago"))
HISTORY_DAYS = 90
HISTORY_WINDOW = {"start_date": "2026-08-09", "end_date": "2026-11-06", "days": 90,
                  "timezone": "America/Chicago"}
DEFAULT_SEED = 20261107
PERSONAS = {
    "usr_maya": {"region": "Dallas, TX", "device": "h_maya_laptop"},
    "usr_dev": {"region": "Austin, TX", "device": "h_dev_phone"},
    "usr_priya": {"region": "Houston, TX", "device": "h_priya_phone"},
    "usr_marcus": {"region": "Dallas, TX", "device": "h_marcus_phone"},
    "usr_elena": {"region": "San Antonio, TX", "device": "h_elena_phone"},
}
OTHER_REGIONS = ("Phoenix, AZ", "Denver, CO", "Miami, FL", "Seattle, WA", "Boston, MA")

# Entire variant groups can be held out by Lane 2b. D-031 fixes code_relay's
# label and variant spelling. Every other threat has multiple distinct groups.
GROUPS = (
    ("takeover", "remote_new_device_swap", 12),
    ("takeover", "local_new_device_swap", 13),
    ("takeover", "rapid_portal_swap", 12),
    ("takeover", "protection_off_swap", 13),
    ("coached", "code_relay", 40),
    ("coached", "fake_support_port_out", 12),
    ("coached", "fake_billing_port_out", 13),
    ("coached", "unverified_care_port_out", 12),
    ("coached", "labeled_support_port_out", 13),
    ("scam_text", "lookalike_account_lock", 10),
    ("scam_text", "lookalike_refund", 10),
    ("scam_text", "pin_request_no_link", 10),
    ("scam_text", "transfer_pin_impostor", 10),
    ("bot", "rapid_failed_logins", 10),
    ("bot", "rotating_regions", 10),
    ("bot", "pin_guess_burst", 10),
    ("bot", "burst_then_success", 10),
    ("recovery_scam", "recovery_call_transfer_pin", 5),
    ("recovery_scam", "recovery_call_account_code", 5),
    ("recovery_scam", "recovery_text_report_fee", 5),
    ("recovery_scam", "recovery_text_unlock", 5),
    ("legit", "travel_login", 8),
    ("legit", "night_shift_login", 8),
    ("legit", "store_phone_upgrade", 8),
    ("legit", "known_family_call", 8),
    ("legit", "routine_account_visit", 8),
)
assert sum(count for _, _, count in GROUPS) == 280


def _event(index: int, uid: str, ordinal: int, kind: str, at: datetime,
           data: dict, call_id: str | None = None) -> dict:
    result = {
        "event_id": f"evt_gen_{index:04d}_{ordinal:02d}",
        "user_id": uid,
        "type": kind,
        "ts": at.isoformat().replace("+00:00", "Z"),
        "source": "generator",
        "data": data,
    }
    if call_id is not None:
        result["call_id"] = call_id
    return result


def _portal(index: int, *, hurried: bool, coached: bool = False,
            target: str = "transfer") -> dict:
    return {
        "session_id": f"ses_gen_{index:04d}",
        "page_path": ["/portal", "/portal/security", f"/portal/security/{target}"],
        "ms_per_step": [1300, 900, 700] if hurried else [5200, 23000, 7700],
        "hesitation_ms": 700 if hurried else (34000 if coached else 6500),
        "paste_into_pin": hurried,
        "tab_switches": 3 if coached else 0,
        "pointer_speed": 1.1 if hurried else 0.43,
        "typing_rhythm_distance": 1.7 if hurried else 0.35,
    }


def _call(index: int, caller_name: str | None, *, verified: bool = False,
          seen_before: bool = False, scam_label: bool = False) -> dict:
    return {
        "direction": "in",
        "other_number_hash": f"h_caller_gen_{index:04d}",
        "caller_name": caller_name,
        "attestation": "A" if verified else ("C" if index % 2 else "B"),
        "seen_before": seen_before,
        "scam_label": scam_label,
    }


def _remote_region(rng: random.Random, home: str) -> str:
    return rng.choice([region for region in OTHER_REGIONS if region != home])


def _with_line_snapshot(scenario: dict) -> dict:
    """One carrier snapshot at this trigger, never a trail of serving regions."""
    trigger = next(e for e in scenario["events"] if e["event_id"] == scenario["trigger_event_id"])
    if trigger["type"] == "message.forwarded":
        return scenario
    uid = scenario["user_id"]
    region = PERSONAS[uid]["region"]
    if scenario["label"] == "legit":
        logins = [e for e in scenario["events"] if e["type"] == "login" and e["ts"] <= trigger["ts"]]
        if logins:
            region = max(logins, key=lambda e: e["ts"])["data"]["region"]
    # A takeover's remote requester and the customer's phone are independent.
    snapshot = {
        "event_id": scenario["scenario_id"].replace("scn_", "evt_", 1) + "_line_region",
        "user_id": uid, "type": "line.region",
        "ts": (datetime.fromisoformat(trigger["ts"].replace("Z", "+00:00")) - timedelta(seconds=1))
            .isoformat().replace("+00:00", "Z"),
        "source": "generator", "data": {"region": region},
    }
    if trigger.get("call_id"):
        snapshot["call_id"] = trigger["call_id"]
    events = [e for e in scenario["events"] if e["type"] != "line.region"]
    events.insert(next(i for i, e in enumerate(events) if e["event_id"] == trigger["event_id"]), snapshot)
    scenario["events"] = events
    return scenario


def histories(seed: int = DEFAULT_SEED) -> dict[str, list[dict]]:
    """Normal sessions in a fixed 90-day window, sparse at persona cadence."""
    result = {}
    monthly = (0, 30, 60, 89)
    weekly = tuple(range(0, 90, 7)) + (89,)
    for persona_index, (uid, profile) in enumerate(PERSONAS.items()):
        rng = random.Random(seed + 10000 + persona_index)
        events = []

        def add(day: int, hour: int, kind: str, data: dict, minute: int = 0):
            at = (HISTORY_START + timedelta(days=day)).replace(hour=hour, minute=minute)
            events.append({"event_id": f"evt_hist_{uid[4:]}_{len(events) + 1:03d}",
                           "user_id": uid, "type": kind,
                           "ts": at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                           "source": "generator", "data": data})

        for visit, day in enumerate(weekly if uid in {"usr_dev", "usr_marcus"} else monthly):
            hour = rng.randrange(2, 6) if uid == "usr_priya" else rng.randrange(16, 22) if uid == "usr_dev" else rng.randrange(10, 19)
            region = ((profile["region"],) + OTHER_REGIONS)[visit % 6] if uid == "usr_marcus" else profile["region"]
            device = ("h_maya_phone" if visit % 2 else "h_maya_laptop") if uid == "usr_maya" else profile["device"]
            if uid == "usr_dev" and day > 50:
                device = "h_dev_new_phone"
            add(day, hour, "login", {"device_hash": device, "region": region,
                                      "new_device": False, "succeeded": True})
            normal_pace = {"usr_maya": 7000, "usr_dev": 1800, "usr_priya": 4200,
                           "usr_marcus": 2300, "usr_elena": 6500}[uid]
            pace = normal_pace + rng.randrange(-300, 500)
            add(day, hour, "portal.signals", {
                "session_id": f"ses_hist_{uid[4:]}_{visit:02d}",
                "page_path": ["/portal", "/portal/billing" if visit % 2 == 0 else "/portal/plan"],
                "ms_per_step": [pace, pace + 500], "hesitation_ms": rng.randrange(500, 2500),
                "paste_into_pin": False, "tab_switches": rng.randrange(0, 2),
                "pointer_speed": round(rng.uniform(0.3, 0.7), 2),
                "typing_rhythm_distance": round(rng.uniform(0.05, 0.3), 2),
            }, minute=2)
        for day in ((45,) if uid == "usr_maya" else (12, 45, 78) if uid == "usr_elena" else ()):
            add(day, 14, "pin.attempt", {"ok": True, "channel": "care"})
        if uid == "usr_dev":
            add(50, 17, "login", {"device_hash": "h_dev_new_phone", "region": profile["region"],
                                    "new_device": True, "succeeded": True})
            add(50, 17, "sim_swap.requested", {"new_device_hash": "h_dev_new_phone", "channel": "store"}, minute=5)
        if uid in {"usr_dev", "usr_marcus", "usr_elena"}:
            add(65, 16, "protection.changed", {"name": "scam_block", "enabled": True,
                                                "via": "app" if uid != "usr_elena" else "care"})
        result[uid] = sorted(events, key=lambda e: e["ts"])
    return result


def _build(index: int, label: str, variant: str, seed: int) -> dict:
    rng = random.Random(seed + index)
    uid = rng.choice(tuple(PERSONAS))
    if variant == "travel_login":
        uid = "usr_marcus"
    elif variant == "night_shift_login":
        uid = "usr_priya"
    elif variant == "store_phone_upgrade":
        uid = "usr_dev"
    elif variant == "known_family_call":
        uid = "usr_maya"
    p = PERSONAS[uid]
    # Scenarios are independent demo-day sessions, after the normal baseline.
    day = datetime(2026, 11, 7, tzinfo=timezone.utc)
    hour = 8 if variant == "night_shift_login" else (13, 16, 19, 22)[(index - 1) % 4]
    start = day.replace(hour=hour) + timedelta(minutes=rng.randrange(0, 35))
    at = lambda minutes: start + timedelta(minutes=minutes)
    call_id = f"call_gen_{index:04d}"
    ev: list[dict] = []

    def add(kind: str, minutes: int, data: dict, on_call: bool = False) -> None:
        ev.append(_event(index, uid, len(ev) + 1, kind, at(minutes), data,
                         call_id if on_call else None))

    if label == "takeover":
        new_device = f"h_new_device_gen_{index:04d}"
        region = p["region"] if variant == "local_new_device_swap" else _remote_region(rng, p["region"])
        add("login", 0, {"device_hash": new_device, "region": region,
                         "new_device": True, "succeeded": True})
        if variant == "rapid_portal_swap":
            add("portal.signals", 1, _portal(index, hurried=True, target="sim"))
        elif variant == "protection_off_swap":
            add("protection.changed", 1, {"name": "sim_protection", "enabled": False,
                                           "via": "app"})
        elif variant == "local_new_device_swap":
            add("pin.attempt", 1, {"ok": False, "channel": "portal"})
        add("sim_swap.requested", 3, {"new_device_hash": new_device,
                                      "channel": "app" if index % 2 else "portal"})

    elif variant == "code_relay":
        add("call.started", 0, _call(index, rng.choice(("T-Mobile Support", "T-Mobile Account Care"))), True)
        add("otp.sent", rng.randrange(5, 16), {"purpose": "login"}, True)
        trigger = ev[-1]["event_id"]
        if index % 3:
            add("login", 18, {"device_hash": f"h_relay_device_gen_{index:04d}",
                               "region": _remote_region(rng, p["region"]),
                               "new_device": True, "succeeded": True}, True)

    elif label == "coached":
        caller = {
            "fake_support_port_out": "T-Mobile Support",
            "fake_billing_port_out": "T-Mobile Billing",
            "unverified_care_port_out": "T-Mobile Care",
            "labeled_support_port_out": "T-Mobile Support",
        }[variant]
        add("call.started", 0, _call(index, caller,
                                     scam_label=variant == "labeled_support_port_out"), True)
        add("login", 12, {"device_hash": p["device"], "region": p["region"],
                           "new_device": False, "succeeded": True}, True)
        add("portal.signals", 16, _portal(index, hurried=False, coached=True), True)
        add("protection.changed", 18, {"name": "port_out_protection", "enabled": False,
                                        "via": "portal"}, True)
        add("transfer_pin.requested", 20, {}, True)

    elif label == "scam_text":
        domain = f"t-mobile-{rng.choice(('secure', 'billing', 'help'))}-{index:04d}.example"
        messages = {
            "lookalike_account_lock": f"T-Mobile: your account is locked. Verify now at https://{domain}",
            "lookalike_refund": f"T-Mobile refund pending. Confirm your details at https://{domain}",
            "pin_request_no_link": "T-Mobile support: urgent account review. Reply with your account PIN.",
            "transfer_pin_impostor": "T-Mobile transfer team: reply with your number transfer PIN immediately.",
        }
        # Message content is present only because the customer forwarded it.
        add("message.forwarded", 0, {"channel": "imessage" if index % 2 else "sms",
                                      "text": messages[variant],
                                      "from_hash": f"h_sender_gen_{index:04d}"})

    elif label == "bot":
        regions = tuple(OTHER_REGIONS)
        if variant == "pin_guess_burst":
            for step in range(4):
                add("pin.attempt", step, {"ok": False, "channel": "portal"})
            add("login", 5, {"device_hash": f"h_bot_device_gen_{index:04d}",
                              "region": _remote_region(rng, p["region"]),
                              "new_device": True, "succeeded": False})
        else:
            for step in range(4):
                add("login", step, {
                    "device_hash": f"h_bot_device_gen_{index:04d}_{step}" if variant == "rotating_regions"
                                   else f"h_bot_device_gen_{index:04d}",
                    "region": regions[step] if variant == "rotating_regions" else
                              _remote_region(rng, p["region"]),
                    "new_device": True,
                    "succeeded": variant == "burst_then_success" and step == 3,
                })
            if variant == "rapid_failed_logins":
                add("portal.signals", 5, _portal(index, hurried=True))

    elif label == "recovery_scam":
        if variant.startswith("recovery_text_"):
            domain = f"t-mobile-recovery-{index:04d}.example"
            message = (f"Fraud recovery: pay a report fee at https://{domain} to restore your line."
                       if variant == "recovery_text_report_fee" else
                       f"T-Mobile recovery: unlock your account at https://{domain} immediately.")
            add("message.forwarded", 0, {"channel": "imessage", "text": message,
                                          "from_hash": f"h_recovery_sender_gen_{index:04d}"})
        else:
            add("call.started", 0, _call(index, "T-Mobile Fraud Recovery"), True)
            if variant == "recovery_call_transfer_pin":
                add("protection.changed", 14, {"name": "port_out_protection",
                                                "enabled": False, "via": "portal"}, True)
                add("transfer_pin.requested", 16, {}, True)
            else:
                add("otp.sent", 13, {"purpose": "account_change"}, True)

    elif variant == "travel_login":
        add("login", 0, {"device_hash": p["device"],
                         "region": _remote_region(rng, p["region"]),
                         "new_device": False, "succeeded": True})
        add("protection.changed", 5, {"name": "scam_block", "enabled": True,
                                      "via": "app"})
    elif variant == "night_shift_login":
        add("login", 0, {"device_hash": p["device"], "region": p["region"],
                         "new_device": False, "succeeded": True})
        add("pin.attempt", 4, {"ok": True, "channel": "app"})
    elif variant == "store_phone_upgrade":
        new_device = f"h_store_upgrade_gen_{index:04d}"
        add("login", 0, {"device_hash": new_device, "region": p["region"],
                         "new_device": True, "succeeded": True})
        add("sim_swap.requested", 8, {"new_device_hash": new_device, "channel": "store"})
    elif variant == "known_family_call":
        add("call.started", 0, _call(index, None, verified=True, seen_before=True), True)
        add("login", 17, {"device_hash": p["device"], "region": p["region"],
                           "new_device": False, "succeeded": True}, True)
        add("protection.changed", 20, {"name": "scam_block", "enabled": True,
                                        "via": "portal"}, True)
    elif variant == "routine_account_visit":
        add("login", 0, {"device_hash": p["device"], "region": p["region"],
                         "new_device": False, "succeeded": True})
    else:
        raise ValueError(f"Unknown group: {label}/{variant}")

    if variant == "code_relay":
        trigger_id = trigger
    elif label == "bot":
        trigger_id = next(item["event_id"] for item in reversed(ev)
                          if item["type"] == "login")
    elif variant == "travel_login":
        trigger_id = ev[0]["event_id"]
    else:
        trigger_id = ev[-1]["event_id"]
    return _with_line_snapshot({
        "scenario_id": f"scn_gen_{index:04d}",
        "user_id": uid,
        "label": label,
        "hard_negative": label == "legit" and variant != "routine_account_visit",
        "trigger_event_id": trigger_id,
        "events": ev,
        "generator": {"seed": seed + index, "variant": variant},
    })


def scenarios(seed: int = DEFAULT_SEED) -> list[dict]:
    result: list[dict] = []
    for label, variant, count in GROUPS:
        for _ in range(count):
            result.append(_build(len(result) + 1, label, variant, seed))
    return result


def _expected_trigger_type(label: str, variant: str) -> str:
    if label == "takeover" or variant == "store_phone_upgrade":
        return "sim_swap.requested"
    if variant == "code_relay" or variant == "recovery_call_account_code":
        return "otp.sent"
    if label == "coached" or variant == "recovery_call_transfer_pin":
        return "transfer_pin.requested"
    if label == "scam_text" or variant.startswith("recovery_text_"):
        return "message.forwarded"
    if label == "bot" or variant in ("travel_login", "routine_account_visit"):
        return "login"
    if variant == "night_shift_login":
        return "pin.attempt"
    if variant == "known_family_call":
        return "protection.changed"
    raise ValueError(f"Unknown group: {label}/{variant}")


def _validate_snapshot(scenario: dict) -> None:
    events = scenario["events"]
    trigger_index = next(i for i, event in enumerate(events)
                         if event["event_id"] == scenario["trigger_event_id"])
    snapshots = [event for event in events if event["type"] == "line.region"]
    if events[trigger_index]["type"] == "message.forwarded":
        if snapshots:
            raise ValueError(f"{scenario['scenario_id']}: forwarded text needs no serving-region snapshot")
        return
    if len(snapshots) != 1 or trigger_index == 0 or events[trigger_index - 1] != snapshots[0]:
        raise ValueError(f"{scenario['scenario_id']}: expected one snapshot immediately before trigger")
    if snapshots[0]["ts"] >= events[trigger_index]["ts"]:
        raise ValueError(f"{scenario['scenario_id']}: snapshot must precede trigger")


def write_or_check(seed: int = DEFAULT_SEED, output_dir: Path = SCENARIO_DIR,
                   *, check: bool = False) -> tuple[Counter, Counter]:
    labels: Counter = Counter()
    variants: Counter = Counter()
    generated = scenarios(seed)
    expected_names = {f"generated_{scenario['scenario_id'].split('_')[-1]}.json"
                      for scenario in generated}
    if check:
        actual_names = {path.name for path in output_dir.glob("generated_*.json")}
        if actual_names != expected_names:
            raise ValueError(f"generated file set differs: missing={sorted(expected_names - actual_names)}, "
                             f"extra={sorted(actual_names - expected_names)}")
    for scenario in generated:
        violations = errors("DatasetScenario", scenario)
        if violations:
            raise ValueError(f"{scenario['scenario_id']}: {violations}")
        _validate_snapshot(scenario)
        triggers = [item for item in scenario["events"]
                    if item["event_id"] == scenario["trigger_event_id"]]
        expected_type = _expected_trigger_type(scenario["label"],
                                                scenario["generator"]["variant"])
        if len(triggers) != 1 or triggers[0]["type"] != expected_type:
            raise ValueError(f"{scenario['scenario_id']}: trigger must be one {expected_type}")
        if scenario["label"] == "bot":
            last_login = next(item for item in reversed(scenario["events"])
                              if item["type"] == "login")
            if triggers[0] != last_login:
                raise ValueError(f"{scenario['scenario_id']}: bot trigger must be final login")
        labels[scenario["label"]] += 1
        variants[scenario["generator"]["variant"]] += 1
        path = output_dir / f"generated_{scenario['scenario_id'].split('_')[-1]}.json"
        content = json.dumps(scenario, indent=2, ensure_ascii=False) + "\n"
        if check:
            if not path.is_file() or path.read_text() != content:
                raise ValueError(f"{path}: missing or differs from seed {seed}")
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    return labels, variants


def write_or_check_history(seed: int = DEFAULT_SEED, output_dir: Path = HISTORY_DIR,
                           *, check: bool = False) -> dict[str, int]:
    personas = json.loads((DATA_DIR / "personas.json").read_text())
    if personas.get("history_window") != HISTORY_WINDOW:
        raise ValueError("personas.json history_window differs from generator's 90-day window")
    generated = histories(seed)
    expected_names = {f"{uid}.jsonl" for uid in generated}
    if check and {path.name for path in output_dir.glob("*.jsonl")} != expected_names:
        raise ValueError("history file set differs from five personas")
    counts = {}
    for uid, events in generated.items():
        for event in events:
            violations = errors("Event", event)
            if violations:
                raise ValueError(f"{event['event_id']}: {violations}")
            if event["type"] == "line.region":
                raise ValueError("baseline history must not contain serving-region trails")
            local_day = datetime.fromisoformat(event["ts"].replace("Z", "+00:00")).astimezone(HISTORY_START.tzinfo).date()
            if not HISTORY_START.date() <= local_day < (HISTORY_START + timedelta(days=HISTORY_DAYS)).date():
                raise ValueError(f"{event['event_id']}: outside the 90-day window")
        path = output_dir / f"{uid}.jsonl"
        content = "".join(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n" for event in events)
        if check:
            if not path.is_file() or path.read_text() != content:
                raise ValueError(f"{path}: missing or differs from seed {seed}")
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        counts[uid] = len(events)
    return counts


def validate_seeds() -> int:
    paths = sorted(SCENARIO_DIR.glob("seed_*.json"))
    if len(paths) != 20:
        raise ValueError("expected the original 20 hand-authored seed scenarios")
    for path in paths:
        scenario = json.loads(path.read_text())
        violations = errors("DatasetScenario", scenario)
        if violations:
            raise ValueError(f"{path}: {violations}")
        _validate_snapshot(scenario)
    return len(paths)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--check", action="store_true",
                        help="validate and compare generated files without writing")
    args = parser.parse_args()
    labels, variants = write_or_check(args.seed, check=args.check)
    history_counts = write_or_check_history(args.seed, check=args.check)
    seed_count = validate_seeds()
    print(f"{'checked' if args.check else 'wrote'} {sum(labels.values())} generated scenarios")
    print(f"validated {seed_count} seeds; {seed_count + sum(labels.values())} total scenarios")
    print("history window:", HISTORY_WINDOW)
    print("history events:", history_counts)
    print("labels:", dict(sorted(labels.items())))
    print("variants:", dict(sorted(variants.items())))


if __name__ == "__main__":
    main()
