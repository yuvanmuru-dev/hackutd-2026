"""Titan brain. Every door (web, messaging, voice, watcher, console) talks to this API only.

Run:   cd agent && MOCK=1 uvicorn server:app --reload --port 8000
Docs:  http://localhost:8000/docs      Contract: contracts/schema.json (v0.3), docs/CONTRACTS.md

MOCK=1 (default for now): real gate rules + in-memory store, and workflow runs replay the fixture run
step by step (MOCK_STEP_MS, default 400). The real Nemotron workflow replaces the replay, same StepEvents.
"""
from __future__ import annotations

import asyncio
import json
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from core import gate, mock_runs
from core.contracts import require
from core.events import _case_for_call, ingest
from core.store import iso, new_id, now, store

MOCK = os.getenv("MOCK", "1") == "1"
app = FastAPI(title="Titan brain", version="0.3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_tasks: set[asyncio.Task] = set()

TOOLS = [  # what the Context/Risk agents can call (Lane 2a/2b implement; names are fixed)
    {"name": "account_history", "description": "Usual devices, regions, hours, change frequency, care channel"},
    {"name": "device_sim_status", "description": "Device age on the line, SIM changed recently"},
    {"name": "protection_status", "description": "Protection state, recent toggles, codes, transfer PINs"},
    {"name": "call_context", "description": "Active call? duration, seen before, caller-ID verification, scam label"},
    {"name": "location_match", "description": "Is the requesting device in the same region as the line"},
    {"name": "portal_signals", "description": "Derived portal behavior for the session"},
    {"name": "check_message", "description": "Lookalike domain, RDAP domain age, URLhaus"},
    {"name": "recent_scam_reports", "description": "Numbers/domains already reported"},
    {"name": "policy_lookup", "description": "Carrier security policy + FTC guidance (NeMo Retriever)"},
    {"name": "ml.score", "description": "Anomaly + calibrated risk score with top reasons (Lane 2b)"},
]


def _start(case_id: str, trigger: str):
    case = store.cases[case_id]
    if trigger == "heads_up":
        mock_runs.heads_up(store, case)
        return
    task = asyncio.create_task(mock_runs.replay(store, case, trigger))  # real workflow plugs in here when MOCK=0
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _user(uid: str) -> dict:
    u = store.user(uid)
    if not u:
        raise HTTPException(404, {"error": f"unknown user {uid}"})
    return u


def _case(cid: str) -> dict:
    c = store.cases.get(cid)
    if not c:
        raise HTTPException(404, {"error": f"unknown case {cid}"})
    return c


@app.get("/health")
async def health():
    return {"ok": True, "mock": MOCK, "version": "0.3", "users": len(store.users), "cases": len(store.cases)}


@app.get("/tools")
async def tools():
    return TOOLS


# ---------- users, timeline
@app.get("/users")
async def users():
    return list(store.users.values())


@app.get("/users/{uid}/timeline")
async def timeline(uid: str):
    _user(uid)
    return store.timeline(uid)


# ---------- events (doors, console, watcher)
@app.post("/events")
async def post_event(request: Request):
    ev = require("Event", await request.json())
    _user(ev["user_id"])
    result = ingest(store, ev)
    if result["trigger"]:
        _start(result["case_id"], result["trigger"])
    return {"accepted": not result["duplicate"], "duplicate": result["duplicate"], "case_id": result["case_id"],
            "trigger": result["trigger"]}


# ---------- fast gate + mock T-Mobile protections (portal)
@app.post("/check")
async def check(request: Request):
    req = require("CheckRequest", await request.json())
    _user(req["user_id"])
    res = gate.check(store, req)
    if res["decision"] == "block" and req.get("customer_choice") == "on_call_help":
        call = store.active_call(req["user_id"])
        if call:  # customer tapped "I'm on a call: help me": Titan steps in now
            case = _case_for_call(store, req["user_id"], call["call_id"], "Customer asked for help during an unverified call")
            res["case_id"] = case["case_id"]
            if not case["run_running"]:
                _start(case["case_id"], "coached")
    return require("CheckResponse", res)


@app.get("/protections/{uid}")
async def protections(uid: str):
    _user(uid)
    return store.protection_state(uid)


@app.post("/protections/{uid}/{name}")
async def change_protection(uid: str, name: str, request: Request):
    _user(uid)
    if name not in ("sim_protection", "port_out_protection", "scam_block"):
        raise HTTPException(404, {"error": f"unknown protection {name}"})
    body = require("ProtectionChangeRequest", await request.json())
    if not body["enabled"] and body["via"] == "portal":
        chk = store.checks.get(body.get("check_id", ""))
        if store.suspicious(store.active_call(uid)) and not (chk and chk["user_id"] == uid and chk["decision"] == "allow"):
            raise HTTPException(409, {"error": "pause_required", "detail": ["Call POST /check first; turning protection off during an unverified call needs the pause screen"]})
    ev = {"event_id": new_id("evt"), "user_id": uid, "type": "protection.changed", "ts": iso(now()), "source": "portal",
          "call_id": None, "data": {"name": name, "enabled": body["enabled"], "via": body["via"]}}
    ingest(store, ev)
    store.set_protection(uid, name, body["enabled"])
    return store.protection_state(uid)


@app.post("/transfer-pin/{uid}")
async def transfer_pin(uid: str):
    """Portal 'Generate transfer PIN'. Gate decides allow vs hold; the event may start a run."""
    _user(uid)
    res = gate.check(store, {"user_id": uid, "action": "transfer_pin"})
    ev = {"event_id": new_id("evt"), "user_id": uid, "type": "transfer_pin.requested", "ts": iso(now()), "source": "portal",
          "call_id": None, "data": {}}
    out = ingest(store, ev)
    if res["decision"] == "hold":
        store.hold_transfer_pin(uid)
    else:
        store.transfer_pins[uid] = {"status": "active", "hold_until": None}
    if out["trigger"]:
        _start(out["case_id"], out["trigger"])
    res["case_id"] = out["case_id"]
    return {"check": require("CheckResponse", res), "protections": store.protection_state(uid)}


# ---------- cases
@app.get("/cases")
async def cases(user_id: str | None = None):
    return [store.case_head(c) for c in store.cases.values() if not user_id or c["user_id"] == user_id]


@app.get("/cases/{cid}")
async def case(cid: str):
    _case(cid)
    return store.case_detail(cid)


@app.get("/cases/{cid}/stream")
async def case_stream(cid: str, request: Request):
    """SSE. `event: step` per StepEvent (replays history first), `event: case` with the case head after each step."""
    c = _case(cid)

    async def gen():
        i, idle = 0, 0.0
        while True:
            if await request.is_disconnected():
                return
            sent = False
            while i < len(c["steps"]):
                s = c["steps"][i]
                i += 1
                sent = True
                yield f"event: step\ndata: {json.dumps(s)}\n\n"
                yield f"event: case\ndata: {json.dumps(store.case_head(c))}\n\n"
                if s["type"] == "done":
                    return
            if not sent:
                await asyncio.sleep(0.2)
                idle += 0.2
                if idle >= 10:
                    idle = 0
                    yield ": keep-alive\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/cases/{cid}/events")
async def case_event(cid: str, request: Request):
    c = _case(cid)
    body = require("CaseEventRequest", await request.json())
    channel = body["channel"] if body["channel"] != "web" else "imessage"
    msg = {"message_id": new_id("msg"), "case_id": cid, "channel": channel, "direction": body["direction"],
           "kind": "transcript" if body["kind"] == "transcript" else ("reply" if body["direction"] == "in" else "info"),
           "text": body["text"], "ts": iso(now())}
    c["messages"].append(msg)
    store.add_step(c, new_id("run"), body.get("agent", "system"), "reach", "transcript" if body["kind"] == "transcript" else "message",
                   body["text"][:140], {"message_id": msg["message_id"]})
    return msg


# ---------- approvals
@app.post("/actions/{aid}/approve")
async def approve(aid: str, request: Request):
    body = require("ApprovalRequest", await request.json())
    c, a = store.find_action(aid)
    if not a:
        raise HTTPException(404, {"error": f"unknown action {aid}"})
    if a["direction"] == "looser" and store.suspicious(store.active_call(c["user_id"])):
        raise HTTPException(409, {"error": "unsafe_now", "detail": ["Can't loosen protection while a suspicious call is active"]})
    a.update(status="applied", approved_via=body["via"], applied_at=iso(now()))
    store.add_step(c, new_id("run"), "system", "recover", "approved", f"Approved via {body['via']}: {a['description']}", {"action_id": aid})
    return a


@app.post("/actions/{aid}/reject")
async def reject(aid: str, request: Request):
    body = require("ApprovalRequest", await request.json())
    c, a = store.find_action(aid)
    if not a:
        raise HTTPException(404, {"error": f"unknown action {aid}"})
    a.update(status="rejected", approved_via=body["via"])
    return a


# ---------- demo helpers (console)
@app.get("/demo/outbox")
async def outbox():
    """What the brain asked messaging/voice to send (useful before those doors exist)."""
    return store.outbox[-50:]


@app.post("/demo/reset")
async def reset():
    store.reset()
    return {"ok": True}


@app.post("/demo/play/{scenario}")
async def play(scenario: str):
    """Inject a scenario's events with real timing compressed. t2 = coached victim, t1 = takeover, t3 = scam text."""
    uid = "usr_maya"

    def ev(typ, data, source="console"):
        return {"event_id": new_id("evt"), "user_id": uid, "type": typ, "ts": iso(now()), "source": source, "call_id": None, "data": data}

    async def run():
        if scenario == "t2":
            seq = [ev("call.started", {"direction": "in", "other_number_hash": "h_8f2c19", "caller_name": "T-Mobile Support",
                                       "attestation": "C", "seen_before": False, "scam_label": False}, "voice"),
                   ev("login", {"device_hash": "h_maya_laptop", "region": "Dallas, TX", "new_device": False, "succeeded": True}, "portal"),
                   ev("protection.changed", {"name": "port_out_protection", "enabled": False, "via": "portal"}, "portal"),
                   ev("transfer_pin.requested", {}, "portal")]
        elif scenario == "t1":
            seq = [ev("login", {"device_hash": "h_unknown_win11", "region": "Lagos, NG", "new_device": True, "succeeded": True}, "portal"),
                   ev("sim_swap.requested", {"new_device_hash": "h_unknown_esim", "channel": "portal"}, "portal")]
        elif scenario == "t3":
            seq = [ev("message.forwarded", {"channel": "imessage", "text": "T-Mobile: your account is locked. Verify now at t-mobile-secure-help.co", "from_hash": "h_31aa02"}, "messaging")]
        else:
            return
        for e in seq:
            e["ts"] = iso(now())
            out = ingest(store, e)
            if out["trigger"]:
                _start(out["case_id"], out["trigger"])
            await asyncio.sleep(1.0)

    if scenario not in ("t1", "t2", "t3"):
        raise HTTPException(404, {"error": "scenario must be t1, t2 or t3"})
    task = asyncio.create_task(run())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"ok": True, "scenario": scenario, "user_id": uid}
