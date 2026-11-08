#!/usr/bin/env python3
"""Independently check the sealed synthetic cohort without scoring it.

Only the raw cohort, its manifest/design, allowed legacy scenario metadata and
history timestamps are read. Diagnostics report positions and invariant names,
never event payloads, forwarded text, or schema error messages containing data.
The manifest's digest covers scenarios.jsonl bytes only (not its own contents).
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
ROOT = Path(__file__).resolve().parents[5]
DATA = ROOT / "agent" / "packs" / "guard" / "data"
sys.path.insert(0, str(ROOT / "agent"))
from core.contracts import errors as contract_errors  # noqa: E402


LEGACY_FAMILIES = frozenset("""
account_lockout_link burst_then_success code_relay code_request_no_link
dev_new_phone_store_upgrade fake_billing_port_out fake_support_port_out
known_family_call labeled_support_port_out lookalike_account_lock lookalike_refund
marcus_usual_device_new_state maya_long_verified_repeat_call
new_device_remote_sim_swap night_shift_login pin_failure_before_swap pin_guess_burst
pin_request_no_link priya_normal_night_shift_pin protection_off_swap
rapid_failed_logins rapid_portal_swap recovery_call_account_code
recovery_call_transfer_pin recovery_text_report_fee recovery_text_unlock
remote_app_sim_swap remote_care_sim_swap remote_new_device_swap
remote_sim_swap_after_portal_path rotating_regions routine_account_visit
sim_reactivation_link store_phone_upgrade transfer_pin_cancel_link
transfer_pin_impostor travel_login unverified_care_port_out
""".split())
NEW_FAMILIES = {
    "ended_call_then_port_out": (9, "coached", False),
    "verified_care_device_replacement": (9, "legit", True),
    "customer_forwarded_service_notice": (6, "legit", False),
}
EXPECTED_LABELS = {
    "takeover": 24, "coached": 24, "scam_text": 24,
    "bot": 12, "recovery_scam": 12, "legit": 42,
}
USERS = frozenset("usr_" + name for name in ("maya", "dev", "priya", "marcus", "elena"))
BASELINE_LIMIT = "2026-11-06T22:02:00Z"
SCENARIO_MINIMUM = "2026-11-08T00:00:00Z"
DESIGN_SEED = 7284883994134891592
BASE_SEED = 2269334185941103781
PAYLOAD_KEYS = {
    "call.started": {"direction", "other_number_hash", "attestation", "seen_before", "scam_label"},
    "call.ended": {"duration_s"},
    "login": {"device_hash", "region", "new_device", "succeeded"},
    "otp.sent": {"purpose"},
    "otp.entered": {"purpose"},
    "pin.attempt": {"ok", "channel"},
    "protection.changed": {"name", "enabled", "via"},
    "transfer_pin.requested": set(),
    "sim_swap.requested": {"new_device_hash", "channel"},
    "portal.signals": {
        "session_id", "page_path", "ms_per_step", "hesitation_ms", "paste_into_pin",
        "tab_switches", "pointer_speed", "typing_rhythm_distance",
    },
    "message.forwarded": {"channel", "text", "from_hash"},
    "line.region": {"region"},
}
ACCOUNT_PATHS = frozenset({
    "/portal", "/portal/security", "/portal/security/port-out", "/portal/security/sim",
    "/portal/security/transfer", "/portal/transfer-pin", "/portal/security/port",
})
HASH_KEYS = frozenset({"session_id", "device_hash", "new_device_hash", "other_number_hash", "from_hash"})
SCENARIO_ID = re.compile(r"^sealed_d053_[0-9a-f]{18}$")
EVENT_ID = re.compile(r"^evt_sealed_[0-9a-f]{18}_[0-9]{2,}$")
CALL_ID = re.compile(r"^call_sealed_[0-9a-f]{18}$")
FRESH_HASH = {
    "session_id": re.compile(r"^ses_sealed_[0-9a-f]{18}$"),
    "device_hash": re.compile(r"^h_sealed_device_[0-9a-f]{18}(?:_[0-9]+)?$"),
    "new_device_hash": re.compile(r"^h_sealed_device_[0-9a-f]{18}(?:_[0-9]+)?$"),
    "other_number_hash": re.compile(r"^h_sealed_caller_[0-9a-f]{18}$"),
    "from_hash": re.compile(r"^h_sealed_sender_[0-9a-f]{18}$"),
}
COARSE_REGION = re.compile(r"^[A-Za-z]+(?:[ -][A-Za-z]+)*, [A-Z]{2}$")
US_STATES = frozenset("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
DOMAIN = re.compile(r"(?<![\w@-])(?:[A-Za-z0-9][A-Za-z0-9-]*\.)+[A-Za-z]{2,}(?![\w-])")
URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s<>]+")
PHONE = re.compile(r"(?<!\w)\+?\d[\d(). -]{7,}\d(?!\w)")
SECRET_VALUE = re.compile(r"\b\d{4,8}\b")


class IntegrityError(Exception):
    """An invariant failed; messages never include payload values."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise IntegrityError(message)


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "JSON contains a duplicate object key")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise IntegrityError("JSON contains a non-finite number")


def parse_json(raw: str | bytes, context: str) -> dict:
    try:
        value = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise IntegrityError(f"{context}: invalid JSON") from None
    require(isinstance(value, dict), f"{context}: expected a JSON object")
    return value


def timestamp(value: str, context: str) -> datetime:
    require(isinstance(value, str), f"{context}: timestamp must be text")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise IntegrityError(f"{context}: invalid timestamp") from None
    require(result.tzinfo is not None, f"{context}: timestamp needs a timezone")
    return result.astimezone(timezone.utc)


def inventory() -> dict:
    """Read only allowed IDs/seeds/labels/families and lawful event metadata."""
    families = defaultdict(lambda: {"labels": set(), "hard_negative": set(), "triggers": set()})
    identifiers: set[str] = set()
    seeds: set[int] = set()
    known_devices: set[str] = set()
    regions: set[str] = set()
    users: set[str] = set()
    paths = sorted((DATA / "scenarios").glob("*.json"))
    require(bool(paths), "legacy scenario inventory is empty")
    for path in paths:
        record = parse_json(path.read_bytes(), "legacy inventory")
        generator = record["generator"]
        family = generator["variant"]
        families[family]["labels"].add(record["label"])
        families[family]["hard_negative"].add(record["hard_negative"])
        identifiers.add(record["scenario_id"])
        seeds.add(generator["seed"])
        users.add(record["user_id"])
        for event in record["events"]:
            identifiers.add(event["event_id"])
            if event.get("call_id"):
                identifiers.add(event["call_id"])
            if event["event_id"] == record["trigger_event_id"]:
                families[family]["triggers"].add(event["type"])
            payload = event["data"]
            # Do not inspect existing forwarded text, caller names, or other content.
            for key in HASH_KEYS:
                if key in payload:
                    identifiers.add(payload[key])
            if event["type"] == "login":
                regions.add(payload["region"])
                if not payload["new_device"]:
                    known_devices.add(payload["device_hash"])
            elif event["type"] == "line.region":
                regions.add(payload["region"])
    require(set(families) == LEGACY_FAMILIES, "source family set differs from the frozen 38-family inventory")
    require(users == USERS, "source inventory does not contain the five expected users")
    for metadata in families.values():
        require(len(metadata["labels"]) == len(metadata["hard_negative"]) == 1,
                "source family has inconsistent labels or hard-negative membership")

    baseline_max = None
    history_users: set[str] = set()
    history_count = 0
    baseline_by_user: dict[str, datetime] = {}
    for path in sorted((DATA / "history").glob("*.jsonl")):
        history_users.add(path.stem)
        for raw in path.read_bytes().splitlines():
            require(bool(raw.strip()), "baseline history contains a blank record")
            # Baseline access is deliberately limited to the timestamp field.
            ts = timestamp(parse_json(raw, "baseline timestamp")["ts"], "baseline timestamp")
            history_count += 1
            baseline_max = ts if baseline_max is None else max(ts, baseline_max)
            baseline_by_user[path.stem] = max(ts, baseline_by_user.get(path.stem, ts))
    require(history_users == USERS, "baseline history files do not cover exactly the five users")
    require(baseline_max is not None, "baseline timestamp inventory is empty")
    require(baseline_max <= timestamp(BASELINE_LIMIT, "fixed baseline bound"), "baseline exceeds the frozen maximum timestamp")
    return {
        "families": families, "identifiers": identifiers, "seeds": seeds,
        "known_devices": known_devices, "regions": regions, "baseline_max": baseline_max,
        "history_count": history_count, "source_count": len(paths), "baseline_by_user": baseline_by_user,
    }


def check_text(text: str, benign: bool, context: str) -> None:
    require(bool(text.strip()), f"{context}: forwarded text is empty")
    require(not PHONE.search(text), f"{context}: possible phone number in text")
    require(not SECRET_VALUE.search(text), f"{context}: possible PIN/OTP value in text")
    require("@" not in text, f"{context}: possible contact address in text")
    domains = DOMAIN.findall(text)
    links = URL.findall(text)
    require(not benign or not (domains or links), f"{context}: benign notice contains a link or host")
    for domain in domains:
        require(domain.lower().endswith(".example"), f"{context}: non-reserved host")
    for link in links:
        parsed = urlsplit(link.rstrip(".,;!?)\"'"))
        require(parsed.scheme in {"https", "http"} and bool(parsed.hostname), f"{context}: invalid web link")
        require(parsed.hostname.lower().endswith(".example"), f"{context}: non-reserved link host")
        require(parsed.username is None and parsed.password is None, f"{context}: link contains credentials")


def check_call_sequence(events: list[dict], family: str, context: str) -> set[str]:
    starts: dict[str, tuple[int, datetime]] = {}
    ends: dict[str, int] = {}
    for index, event in enumerate(events):
        call_id = event.get("call_id")
        kind = event["type"]
        if kind in {"call.started", "call.ended"}:
            require(bool(call_id), f"{context}: call event has no call reference")
        if kind == "call.started":
            require(call_id not in starts, f"{context}: duplicate call start")
            starts[call_id] = (index, timestamp(event["ts"], context))
        elif call_id:
            require(call_id in starts, f"{context}: event references an unstarted call")
            if kind == "call.ended":
                require(call_id not in ends, f"{context}: duplicate call end")
                start_index, started_at = starts[call_id]
                elapsed = (timestamp(event["ts"], context) - started_at).total_seconds()
                require(index > start_index and elapsed == event["data"]["duration_s"],
                        f"{context}: call duration does not match timestamps")
                ends[call_id] = index
    require(len(starts) <= 1, f"{context}: call history rather than a trigger snapshot")
    if family == "ended_call_then_port_out":
        require(len(starts) == len(ends) == 1, f"{context}: ended-call family needs one completed call")
        end_index = next(iter(ends.values()))
        require(events[-1]["type"] == "transfer_pin.requested", f"{context}: wrong ended-call trigger")
        changes = [i for i, e in enumerate(events) if e["type"] == "protection.changed"
                   and e["data"]["name"] == "port_out_protection" and e["data"]["enabled"] is False]
        require(len(changes) == 1 and end_index < changes[0] < len(events) - 1,
                f"{context}: port protection change must follow hangup and precede trigger")
        call = events[next(iter(starts.values()))[0]]["data"]
        require(call["direction"] == "in" and not call["seen_before"] and call["attestation"] != "A",
                f"{context}: ended-call family lacks unverified unsolicited metadata")
    if family == "verified_care_device_replacement":
        require(len(starts) == 1, f"{context}: care family needs one outbound call")
        call = events[next(iter(starts.values()))[0]]["data"]
        require(call["direction"] == "out" and call["attestation"] == "A" and not call["seen_before"]
                and not call["scam_label"], f"{context}: care call metadata is inconsistent")
        require(events[-1]["type"] == "sim_swap.requested" and events[-1]["data"]["channel"] == "care",
                f"{context}: care family has wrong replacement trigger")
        kinds = [event["type"] for event in events]
        require("pin.attempt" in kinds and "otp.sent" in kinds and "otp.entered" in kinds,
                f"{context}: care family is missing verification events")
        pin_index, sent_index, entered_index = (kinds.index(k) for k in ("pin.attempt", "otp.sent", "otp.entered"))
        require(pin_index < sent_index < entered_index < len(events) - 1,
                f"{context}: care verification is out of order")
        require(events[pin_index]["data"] == {"ok": True, "channel": "care"}
                and events[sent_index]["data"] == events[entered_index]["data"] == {"purpose": "account_change"},
                f"{context}: care verification metadata is inconsistent")
    return set(starts)


def check_dataset(dataset_path: Path, manifest_path: Path) -> dict:
    source = inventory()
    raw = dataset_path.read_bytes()
    require(bool(raw) and raw.endswith(b"\n"), "dataset must be nonempty and end with a newline")
    raw_lines = raw.splitlines()
    require(len(raw_lines) == 138, "dataset must contain exactly 138 lines")
    require(all(line.strip() for line in raw_lines), "dataset contains blank lines")
    records = [parse_json(line, f"line {i}") for i, line in enumerate(raw_lines, 1)]
    manifest = parse_json(manifest_path.read_bytes(), "manifest")
    labels: Counter = Counter()
    families: Counter = Counter()
    users: Counter = Counter()
    event_types: Counter = Counter()
    scenario_ids: set[str] = set()
    event_ids: set[str] = set()
    call_ids: set[str] = set()
    seeds: set[int] = set()
    fresh_owner: dict[str, int] = {}
    benign_ids: list[str] = []
    hard_negative_ids: list[str] = []
    all_times: list[datetime] = []
    namespace_ids: set[str] = set()

    for line_number, record in enumerate(records, 1):
        context = f"line {line_number}"
        schema_errors = contract_errors("DatasetScenario", record)
        require(not schema_errors, f"{context}: DatasetScenario schema violation(s): {len(schema_errors)}")
        family = record["generator"]["variant"]
        seed = record["generator"]["seed"]
        require(family in LEGACY_FAMILIES or family in NEW_FAMILIES, f"{context}: unplanned family")
        require(0 <= seed < 2 ** 63 and seed not in seeds and seed not in source["seeds"]
                and seed not in {BASE_SEED, DESIGN_SEED}, f"{context}: scenario seed is not fresh and unique")
        seeds.add(seed)
        if family in LEGACY_FAMILIES:
            expected = source["families"][family]
            require(record["label"] in expected["labels"] and record["hard_negative"] in expected["hard_negative"],
                    f"{context}: legacy family label or hard-negative mismatch")
        else:
            _, label, hard_negative = NEW_FAMILIES[family]
            require(record["label"] == label and record["hard_negative"] is hard_negative,
                    f"{context}: new family label or hard-negative mismatch")
        require(not record["hard_negative"] or record["label"] == "legit", f"{context}: hard negative is not legitimate")
        scenario_id = record["scenario_id"]
        require(scenario_id not in scenario_ids and scenario_id not in source["identifiers"], f"{context}: scenario ID collision")
        require(SCENARIO_ID.fullmatch(scenario_id) is not None, f"{context}: malformed sealed scenario ID")
        scenario_ids.add(scenario_id)
        namespace_ids.add(scenario_id)
        labels[record["label"]] += 1
        families[family] += 1
        users[record["user_id"]] += 1
        if record["hard_negative"]:
            hard_negative_ids.append(scenario_id)
        events = record["events"]
        require(bool(events), f"{context}: empty events")
        require(events[-1]["event_id"] == record["trigger_event_id"], f"{context}: trigger is not the final event")
        require(sum(e["event_id"] == record["trigger_event_id"] for e in events) == 1,
                f"{context}: trigger does not resolve exactly once")
        forwarded = any(e["type"] == "message.forwarded" for e in events)
        benign = family == "customer_forwarded_service_notice"
        require(not benign or forwarded, f"{context}: benign notice is not forwarded")
        regions = [i for i, event in enumerate(events) if event["type"] == "line.region"]
        if forwarded:
            require(len(events) == 1 and not regions, f"{context}: forwarded scenario must contain only its forwarded trigger")
            require(record["label"] in {"scam_text", "recovery_scam", "legit"}, f"{context}: invalid forwarded label")
            if record["label"] == "legit":
                require(benign, f"{context}: unplanned benign forwarded family")
                benign_ids.append(scenario_id)
        else:
            require(regions == [len(events) - 2], f"{context}: expected one region snapshot immediately before trigger")
            require(events[-1]["type"] in {"login", "otp.sent", "pin.attempt", "protection.changed",
                    "transfer_pin.requested", "sim_swap.requested"}, f"{context}: unsupported requesting trigger")
        if family in LEGACY_FAMILIES:
            require(events[-1]["type"] in source["families"][family]["triggers"], f"{context}: legacy family trigger type changed")

        previous = None
        local_fresh: set[str] = set()
        for event_index, event in enumerate(events, 1):
            event_context = f"{context} event {event_index}"
            kind = event["type"]
            payload = event["data"]
            require(event["user_id"] == record["user_id"], f"{event_context}: user mismatch")
            event_id = event["event_id"]
            require(event_id not in event_ids and event_id not in source["identifiers"], f"{event_context}: event ID collision")
            require(EVENT_ID.fullmatch(event_id) is not None, f"{event_context}: malformed sealed event ID")
            event_ids.add(event_id)
            namespace_ids.add(event_id)
            current = timestamp(event["ts"], event_context)
            require(previous is None or previous <= current, f"{event_context}: events are not chronological")
            require(current > source["baseline_max"] and current >= timestamp(SCENARIO_MINIMUM, "fixed scenario bound"),
                    f"{event_context}: event does not follow baseline and fixed start")
            all_times.append(current)
            previous = current
            require(kind in PAYLOAD_KEYS, f"{event_context}: unsupported content-bearing event type")
            require(set(payload) <= PAYLOAD_KEYS[kind], f"{event_context}: unapproved payload field")
            event_types[kind] += 1
            if kind in {"login", "line.region"}:
                region = payload["region"]
                require(COARSE_REGION.fullmatch(region) is not None and region[-2:] in US_STATES,
                        f"{event_context}: region is not a coarse city/state service region")
            if kind == "portal.signals":
                require(bool(payload["page_path"]) and all(path in ACCOUNT_PATHS for path in payload["page_path"]),
                        f"{event_context}: path is outside first-party carrier account flows")
                if "ms_per_step" in payload:
                    require(len(payload["ms_per_step"]) == len(payload["page_path"]), f"{event_context}: portal step lengths differ")
            if kind == "message.forwarded":
                require(set(payload) == {"channel", "text", "from_hash"}, f"{event_context}: incomplete forwarded event")
                check_text(payload["text"], benign, event_context)
            for key in HASH_KEYS & payload.keys():
                value = payload[key]
                is_known = kind == "login" and key == "device_hash" and not payload["new_device"]
                if is_known:
                    require(value in source["known_devices"], f"{event_context}: established device is absent from baseline inventory")
                else:
                    require(isinstance(value, str) and FRESH_HASH[key].fullmatch(value) is not None,
                            f"{event_context}: malformed sealed identifier or hash")
                    require(value not in source["identifiers"], f"{event_context}: fresh identifier collides with source inventory")
                    require(value not in fresh_owner or fresh_owner[value] == line_number,
                            f"{event_context}: fresh identifier reused across scenarios")
                    fresh_owner[value] = line_number
                    local_fresh.add(value)
        local_calls = check_call_sequence(events, family, context)
        require(not (local_calls & (call_ids | source["identifiers"])), f"{context}: call ID collision")
        require(all(CALL_ID.fullmatch(call_id) for call_id in local_calls), f"{context}: malformed sealed call ID")
        call_ids.update(local_calls)
        namespace_ids.update(local_calls)
        require(not (local_fresh & namespace_ids), f"{context}: hash/session collides with scenario/event/call namespace")

    require(set(users) == USERS, "cohort does not cover exactly five existing users")
    require(dict(labels) == EXPECTED_LABELS, "label counts differ from fixed design")
    expected_families = {family: 3 for family in LEGACY_FAMILIES}
    expected_families.update({family: count for family, (count, _, _) in NEW_FAMILIES.items()})
    require(dict(families) == expected_families, "family counts differ from fixed 38x3 plus 9/9/6 design")
    require(len(hard_negative_ids) == 33, "expected exactly 33 hard negatives")
    require(len(benign_ids) == 6, "expected exactly six benign forwarded scenarios")
    require(len(namespace_ids) == len(scenario_ids) + len(event_ids) + len(call_ids), "cross-kind ID namespace collision")
    require(not (set(fresh_owner) & namespace_ids), "hash/session collides with an ID namespace")
    summary = {
        "scenario_count": len(records), "family_count": len(families),
        "legacy_family_count": len(LEGACY_FAMILIES), "new_family_count": len(NEW_FAMILIES),
        "label_counts": dict(sorted(labels.items())), "family_counts": dict(sorted(families.items())),
        "user_counts": dict(sorted(users.items())), "hard_negative_count": len(hard_negative_ids),
        "benign_forwarded_count": len(benign_ids), "event_count": len(event_ids),
        "event_type_counts": dict(sorted(event_types.items())), "call_count": len(call_ids),
        "seed_count": len(seeds), "sha256": hashlib.sha256(raw).hexdigest(),
        "byte_count": len(raw), "baseline_max_timestamp": source["baseline_max"].isoformat().replace("+00:00", "Z"),
        "earliest_event_timestamp": min(all_times).isoformat().replace("+00:00", "Z"),
        "latest_event_timestamp": max(all_times).isoformat().replace("+00:00", "Z"),
    }
    check_manifest(manifest, summary, records, benign_ids, hard_negative_ids, source)
    return summary


def check_manifest(manifest: dict, summary: dict, records: list[dict], benign_ids: list[str],
                   hard_negative_ids: list[str], source: dict) -> None:
    """Cross-check metadata without trusting generator implementation checks."""
    require(manifest.get("dataset_file") == "scenarios.jsonl", "manifest must name only the raw dataset file")
    require(manifest.get("dataset_sha256") == summary["sha256"], "manifest raw dataset SHA-256 mismatch")
    metadata_fields = {
        "record_count": "scenario_count", "labels": "label_counts", "family_counts": "family_counts",
        "hard_negative_count": "hard_negative_count", "benign_forwarded_text_count": "benign_forwarded_count",
        "user_counts": "user_counts", "baseline_latest_timestamp": "baseline_max_timestamp",
    }
    for manifest_key, summary_key in metadata_fields.items():
        require(manifest.get(manifest_key) == summary[summary_key], f"manifest {manifest_key} mismatch")
    require(manifest.get("benign_scenario_ids") == benign_ids, "manifest benign-forwarded IDs mismatch")
    require(manifest.get("existing_families") == sorted(LEGACY_FAMILIES), "manifest existing-family inventory mismatch")
    new_families = manifest.get("new_families")
    require(isinstance(new_families, list) and len(new_families) == 3 and set(new_families) == set(NEW_FAMILIES),
            "manifest new-family inventory mismatch")
    require(manifest.get("scenario_seeds") == {r["scenario_id"]: r["generator"]["seed"] for r in records},
            "manifest scenario seed inventory mismatch")
    require(manifest.get("design_seed") == DESIGN_SEED and manifest.get("base_seed") == BASE_SEED,
            "manifest frozen design/base seed mismatch")
    require(manifest.get("scenario_start_floor") == SCENARIO_MINIMUM, "manifest scenario floor mismatch")
    baseline_by_user = {user: ts.isoformat().replace("+00:00", "Z") for user, ts in source["baseline_by_user"].items()}
    require(manifest.get("baseline_latest_by_user") == baseline_by_user, "manifest per-user baseline maxima mismatch")
    rationale = manifest.get("new_family_rationale")
    require(isinstance(rationale, dict) and set(rationale) == set(NEW_FAMILIES)
            and all(isinstance(value, str) and value.strip() for value in rationale.values()),
            "manifest new-family rationale is missing")
    privacy = manifest.get("privacy", {})
    require(all(privacy.get(key) is True for key in (
        "all_data_synthetic", "call_metadata_only", "free_text_only_customer_forwarded",
        "no_contacts_or_cut_data", "no_pin_or_otp_values")), "manifest privacy declarations are incomplete")
    require(privacy.get("reserved_scam_domains") == ".example", "manifest reserved-host declaration mismatch")
    blinding = manifest.get("blinding", {})
    require(all(blinding.get(key) is True for key in ("independent_author", "design_fixed_before_generation"))
            and all(blinding.get(key) is False for key in ("network_access", "outcome_tuning"))
            and blinding.get("publication") == "local_unpublished", "manifest blinding declarations are incomplete")
    # Derive the planned seed set independently from the frozen seeds/counts.
    expected_seeds: dict[str, set[int]] = {}
    for family, count in summary["family_counts"].items():
        expected_seeds[family] = {
            int.from_bytes(hashlib.sha256(f"{BASE_SEED}:{DESIGN_SEED}:{family}:{rep}".encode()).digest()[:8], "big")
            & ((1 << 63) - 1) for rep in range(count)
        }
    actual_seeds: dict[str, set[int]] = defaultdict(set)
    for record in records:
        actual_seeds[record["generator"]["variant"]].add(record["generator"]["seed"])
    require(dict(actual_seeds) == expected_seeds, "scenario seeds do not match the frozen SHA-256 derivation")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("scenarios.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    args = parser.parse_args()
    try:
        result = check_dataset(args.dataset, args.manifest)
    except IntegrityError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    except (OSError, KeyError, TypeError, ValueError, AttributeError):
        print(json.dumps({"status": "failed", "error": "missing, unreadable, or malformed input metadata"}), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", **result}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
