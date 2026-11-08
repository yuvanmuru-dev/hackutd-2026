"""Deliver synthetic repeat-call metadata to the brain during an active watch.

No data APIs, carrier actions, customer texts, or reasoning live here.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import threading
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "contracts/schema.json").read_text())


def validate(name, value):
    Draft202012Validator({"$ref": f"#/$defs/{name}", "$defs": SCHEMA["$defs"]},
                         format_checker=FormatChecker()).validate(value)


def instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timezone required")
    return result


@dataclass(frozen=True)
class Watch:
    case_id: str
    user_id: str
    number_hash: str
    start: datetime
    until: datetime


def active_watch(detail, now):
    validate("CaseDetail", detail)
    if detail["status"] != "watching" or not detail["call"]:
        return None
    if not any(a["kind"] == "report_number" and a["status"] == "applied" for a in detail["actions"]):
        return None
    plans = [s for s in detail["steps"] if s["stage"] == "watch" and s["type"] == "plan" and s["data"].get("until")]
    if not plans:
        return None
    plan = max(plans, key=lambda s: s["seq"])
    start, until = instant(plan["ts"]), instant(plan["data"]["until"])
    if not start <= now < until:
        return None
    calls = [e for e in detail["timeline"] if e["type"] == "call.started"
             and e.get("call_id") == detail["call"]["call_id"]]
    if not calls:
        return None
    number_hash = max(calls, key=lambda e: e["ts"])["data"]["other_number_hash"]
    if not number_hash or re.fullmatch(r"\+?\d{7,15}", number_hash):
        raise ValueError("Expected a number hash, not a phone number")
    return Watch(detail["case_id"], detail["user_id"], number_hash, start, until)


class Brain:
    def __init__(self, base):
        self.base = base.rstrip("/")

    def request(self, path, body=None):
        req = Request(self.base + path, data=None if body is None else json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10) as response:
            return json.load(response)

    def watches(self, now):
        result = []
        for head in self.request("/cases"):
            if head["status"] != "watching":
                continue
            watch = active_watch(self.request("/cases/" + head["case_id"]), now)
            if watch:
                result.append(watch)
        return result

    def post(self, event):
        validate("Event", event)
        result = self.request("/events", event)
        if not (result.get("accepted") or result.get("duplicate")):
            raise ValueError("Brain did not accept the event")
        return result


def repeat_event(watch, event_id, now):
    """A deliberate synthetic demo call, not a claim of a real carrier event."""
    token = hashlib.sha256(event_id.encode()).hexdigest()[:24]
    event = {"event_id": event_id, "user_id": watch.user_id, "type": "call.started",
             "ts": now.isoformat().replace("+00:00", "Z"), "source": "watcher", "call_id": f"call_watch_{token}",
             "data": {"direction": "in", "other_number_hash": watch.number_hash,
                      "caller_name": "Fraud recovery department (demo)", "attestation": "none",
                      "seen_before": True, "scam_label": False}}
    validate("Event", event)
    return event


def matches(event, watches, now):
    validate("Event", event)
    if event["type"] != "call.started" or event["data"]["direction"] != "in":
        return False
    occurred = instant(event["ts"])
    return any(w.user_id == event["user_id"] and w.number_hash == event["data"]["other_number_hash"]
               and w.start <= occurred <= now < w.until for w in watches)


class Queue:
    def __init__(self, calls_file, state_file):
        self.calls_file, self.state_file = Path(calls_file), Path(state_file)
        self.sent = set()
        if self.state_file.exists():
            self.sent = set(json.loads(self.state_file.read_text())["sent"])

    def save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"sent": sorted(self.sent)}))
        tmp.chmod(0o600)
        tmp.replace(self.state_file)

    def once(self, brain, now):
        watches = brain.watches(now)
        if not self.calls_file.exists():
            return 0
        if self.calls_file.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("Metadata queue is too large")
        count = 0
        for line in self.calls_file.read_text().splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            key = hashlib.sha256(event["event_id"].encode()).hexdigest()
            if key in self.sent or not matches(event, watches, now):
                continue
            # Keep the producer's event ID, so a crash after POST is safe to retry.
            brain.post({**event, "source": "watcher"})
            self.sent.add(key)
            self.save()
            count += 1
        return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--repeat-case", help="Emit one synthetic repeat call for a reported-number case")
    parser.add_argument("--event-id", help="Stable evt_ ID; reuse it if retrying the same demo call")
    parser.add_argument("--calls", default=os.getenv("WATCHER_CALLS_FILE", ".state/incoming.jsonl"))
    parser.add_argument("--state", default=os.getenv("WATCHER_STATE_FILE", ".state/checkpoint.json"))
    args = parser.parse_args()
    brain = Brain(os.getenv("BRAIN_URL", "http://localhost:8000"))
    clock = lambda: datetime.now(timezone.utc)
    if args.repeat_case:
        if not args.event_id or not args.event_id.startswith("evt_"):
            parser.error("--repeat-case requires a stable --event-id evt_...")
        now = clock()
        watch = next((w for w in brain.watches(now) if w.case_id == args.repeat_case), None)
        if not watch:
            parser.error("Case must have an active watch and an applied number report")
        result = brain.post(repeat_event(watch, args.event_id, now))
        print(json.dumps({"event": "repeat_call_posted", "duplicate": result.get("duplicate", False)}))
        return
    interval = float(os.getenv("WATCHER_INTERVAL_S", "60"))
    if interval < 1:
        parser.error("WATCHER_INTERVAL_S must be at least 1")
    queue = Queue(args.calls, args.state)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    while not stop.is_set():
        try:
            print(json.dumps({"event": "watcher_tick", "posted": queue.once(brain, clock())}), flush=True)
        except Exception:
            print(json.dumps({"event": "watcher_tick_failed"}), flush=True)
            if args.once:
                raise SystemExit(1) from None
        if args.once:
            break
        stop.wait(interval)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Exceptions may include URLs or payload snippets; keep logs metadata-only.
        print(json.dumps({"event": "watcher_failed"}))
        raise SystemExit(1) from None
