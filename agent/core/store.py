"""In-memory store with the same shape as the Supabase schema (docs/DATABASE.md).

Used by MOCK=1, tests, and as the fallback when Supabase is not configured.
Lane 5's Supabase store must expose the same methods.
"""
from __future__ import annotations

import itertools
import threading
from datetime import datetime, timedelta, timezone

from core.contracts import fixture

UNVERIFIED = {"B", "C", "none"}
PROTECTION_NAMES = ("sim_protection", "port_out_protection", "scam_block")


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat().replace("+00:00", "Z") if dt else None


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


_counter = itertools.count(1)


def new_id(prefix: str) -> str:
    return f"{prefix}_{int(now().timestamp())}{next(_counter):04d}"


PERSONAS = [
    ("usr_dev", "Dev", "24, student. New phone every year, does everything in the app."),
    ("usr_priya", "Priya", "41, ER nurse on nights. Logs in between 2 and 5am."),
    ("usr_marcus", "Marcus", "35, sales rep. Logs in from a different state most weeks."),
    ("usr_elena", "Elena", "52. Account language Spanish, calls care about roaming."),
]


class Store:
    def __init__(self):
        self.lock = threading.RLock()
        self.reset()

    def reset(self):
        with self.lock:
            maya = fixture("user.maya.json")
            self.users = {maya["user_id"]: maya}
            for uid, name, persona in PERSONAS:
                self.users[uid] = {"user_id": uid, "name": name, "persona": persona, "face_enabled": False}
            t = iso(now())
            self.protections = {uid: {n: {"name": n, "enabled": n != "scam_block", "updated_at": t} for n in PROTECTION_NAMES}
                                for uid in self.users}
            self.transfer_pins = {uid: {"status": "none", "hold_until": None} for uid in self.users}
            self.events: dict[str, dict] = {}
            self.calls: dict[str, dict] = {}
            self.cases: dict[str, dict] = {}
            self.case_by_call: dict[str, str] = {}
            self.checks: dict[str, dict] = {}
            self.outbox: list[dict] = []  # what the brain asked messaging/voice to send

    # ---- users / timeline
    def user(self, uid: str) -> dict | None:
        return self.users.get(uid)

    def active_call(self, uid: str) -> dict | None:
        for c in self.calls.values():
            if c["user_id"] == uid and c["ended_at"] is None:
                return c
        return None

    def call_summary(self, c: dict | None) -> dict | None:
        if not c:
            return None
        end = parse(c["ended_at"]) if c["ended_at"] else now()
        return {k: c[k] for k in ("call_id", "caller_name", "attestation", "seen_before", "scam_label", "started_at", "ended_at")} | {
            "duration_s": max(0, int((end - parse(c["started_at"])).total_seconds()))}

    def suspicious(self, c: dict | None) -> bool:
        return bool(c) and (c["attestation"] in UNVERIFIED or c["scam_label"]) and not c["seen_before"]

    def timeline(self, uid: str) -> dict:
        evs = sorted((e for e in self.events.values() if e["user_id"] == uid), key=lambda e: e["ts"])
        calls = [self.call_summary(c) for c in self.calls.values() if c["user_id"] == uid]
        return {"user_id": uid, "events": evs[-200:], "calls": calls, "active_call": self.call_summary(self.active_call(uid))}

    # ---- protections
    def protection_state(self, uid: str) -> dict:
        tp = self.transfer_pins[uid]
        if tp["status"] == "held" and tp["hold_until"] and parse(tp["hold_until"]) < now():
            tp.update(status="active", hold_until=None)
        return {"user_id": uid, "protections": list(self.protections[uid].values()),
                "shield_mode": self.suspicious(self.active_call(uid)), "transfer_pin": dict(tp)}

    def set_protection(self, uid: str, name: str, enabled: bool):
        self.protections[uid][name] = {"name": name, "enabled": enabled, "updated_at": iso(now())}

    def hold_transfer_pin(self, uid: str, hours: int = 24) -> str:
        until = iso(now() + timedelta(hours=hours))
        self.transfer_pins[uid] = {"status": "held", "hold_until": until}
        return until

    # ---- cases
    def new_case(self, uid: str, title: str, call_id: str | None) -> dict:
        cid = new_id("case")
        t = iso(now())
        case = {"case_id": cid, "case_number": f"TTN-{len(self.cases) + 4821}", "user_id": uid, "title": title,
                "status": "open", "threat": None, "confidence": None, "created_at": t, "updated_at": t,
                "call_id": call_id, "risk": None, "signals": [], "verification": None, "steps": [], "actions": [],
                "messages": [], "summary": None, "data_used": [], "run_running": False}
        self.cases[cid] = case
        if call_id:
            self.case_by_call[call_id] = cid
        return case

    def case_detail(self, cid: str) -> dict | None:
        c = self.cases.get(cid)
        if not c:
            return None
        uid = c["user_id"]
        call = self.calls.get(c["call_id"]) if c["call_id"] else None
        timeline = [e for e in sorted(self.events.values(), key=lambda e: e["ts"])
                    if e["user_id"] == uid and (not c["call_id"] or e.get("call_id") == c["call_id"])]
        keys = ("case_id", "case_number", "user_id", "title", "status", "threat", "confidence", "created_at", "updated_at",
                "risk", "signals", "verification", "steps", "actions", "messages", "summary", "data_used")
        return {k: c[k] for k in keys} | {"user": self.users[uid], "call": self.call_summary(call), "timeline": timeline}

    def case_head(self, c: dict) -> dict:
        return {k: c[k] for k in ("case_id", "case_number", "user_id", "title", "status", "threat", "confidence", "created_at", "updated_at")}

    def add_step(self, case: dict, run_id: str, agent: str, stage: str, type_: str, title: str, data: dict | None = None) -> dict:
        step = {"seq": len(case["steps"]), "case_id": case["case_id"], "run_id": run_id, "ts": iso(now()),
                "agent": agent, "stage": stage, "type": type_, "title": title, "data": data or {}}
        case["steps"].append(step)
        case["updated_at"] = step["ts"]
        return step

    def find_action(self, aid: str) -> tuple[dict, dict] | tuple[None, None]:
        for c in self.cases.values():
            for a in c["actions"]:
                if a["action_id"] == aid:
                    return c, a
        return None, None


store = Store()
