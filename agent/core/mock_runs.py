"""MOCK workflow runs: replay the fixture run step by step so every lane sees realistic, live data.

The real workflow engine (core/workflow.py, Nemotron agents) replaces this; the StepEvents look the same.
Speed: MOCK_STEP_MS (default 400).
"""
from __future__ import annotations

import asyncio
import copy
import os

from core import outbound
from core.contracts import fixture
from core.store import Store, iso, new_id, now

T2 = fixture("case.t2.json")


def _step_ms() -> float:
    return float(os.getenv("MOCK_STEP_MS", "400")) / 1000


def _remap(obj, ids: dict):
    if isinstance(obj, dict):
        return {k: _remap(v, ids) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_remap(v, ids) for v in obj]
    if isinstance(obj, str):
        return ids.get(obj, obj)
    return obj


def _short_run(threat: str) -> dict:
    """A short run for T1 / T3 built from the risk fixtures (T2 replays the full fixture)."""
    risk = fixture("risk.t1.json" if threat == "takeover" else "risk.t3.json")
    if threat == "takeover":
        steps = [("system", "trigger", "plan", "SIM swap requested right after a new-device login", {}),
                 ("context", "context", "tool_call", "device_sim_status · location_match · account_history", {}),
                 ("context", "context", "tool_result", "New device · login from Lagos while her phone is in Dallas", {}),
                 ("risk", "risk", "score", "Account takeover · 93% (calibrated)", {"risk": risk}),
                 ("verifier", "verify", "verify", "4 claims checked · 0 dropped", {}),
                 ("response", "respond", "action", "SIM swap blocked and SIM Protection locked", {"action_kind": "relock"}),
                 ("messaging", "reach", "message", "iMessage sent: \"Was this you? Reply YES or NO\"", {}),
                 ("system", "await", "plan", "Waiting for her reply", {}),
                 ("system", "watch", "done", "Run complete (mock)", {})]
    else:
        steps = [("system", "trigger", "plan", "Customer forwarded a text to Titan", {}),
                 ("context", "context", "tool_call", "check_message: lookalike domain · RDAP age · URLhaus", {}),
                 ("context", "context", "tool_result", "t-mobile-secure-help.co imitates T-Mobile · registered 3 days ago", {}),
                 ("risk", "risk", "score", "Scam text · 96%", {"risk": risk}),
                 ("verifier", "verify", "verify", "3 claims checked · 0 dropped", {}),
                 ("messaging", "reach", "message", "Reply sent: \"This is a scam. Don't tap the link.\"", {}),
                 ("system", "watch", "done", "Run complete (mock)", {})]
    return {"risk": risk, "steps": steps}


async def replay(store: Store, case: dict, threat: str):
    """Append steps to the case over time and apply their side effects (protections, actions, messages)."""
    case["run_running"] = True
    run_id = new_id("run")
    uid = case["user_id"]
    try:
        if threat != "coached":
            plan = _short_run(threat)
            case["threat"], case["risk"], case["confidence"] = threat, plan["risk"], plan["risk"]["confidence"]
            for agent, stage, type_, title, data in plan["steps"]:
                await asyncio.sleep(_step_ms())
                if type_ == "action":
                    store.set_protection(uid, "sim_protection", True)
                    case["actions"].append({"action_id": new_id("act"), "case_id": case["case_id"], "kind": "relock",
                                            "direction": "safer", "status": "applied", "requires_approval": False,
                                            "approved_via": None, "description": title, "created_at": iso(now()), "applied_at": iso(now())})
                if type_ == "message":
                    text = title.split(": ", 1)[-1].strip('"')
                    msg = {"message_id": new_id("msg"), "case_id": case["case_id"], "channel": "imessage", "direction": "out",
                           "kind": "alert", "text": f"Titan: {text}", "ts": iso(now())}
                    case["messages"].append(msg)
                    outbound.send_message(store, {"case_id": case["case_id"], "user_id": uid, "channel": "imessage",
                                                  "kind": "alert", "text": msg["text"], "expects_reply": True, "action_id": None})
                if type_ == "plan" and stage == "await":
                    case["status"] = "awaiting_reply"
                if type_ == "done":
                    case["status"] = "watching"
                store.add_step(case, run_id, agent, stage, type_, title, data)
            return

        ids = {a["action_id"]: new_id("act") for a in T2["actions"]}
        ids |= {m["message_id"]: new_id("msg") for m in T2["messages"]}
        ids |= {"case_t2": case["case_id"], "TTN-4821": case["case_number"], "usr_maya": uid}
        fx_actions = {a["action_id"]: a for a in T2["actions"]}
        fx_messages = {m["message_id"]: m for m in T2["messages"]}
        case["signals"], case["data_used"] = copy.deepcopy(T2["signals"]), list(T2["data_used"])

        def add_action(fx_id: str, status: str):
            a = _remap(copy.deepcopy(fx_actions[fx_id]), ids)
            a.update(status=status, created_at=iso(now()), applied_at=iso(now()) if status == "applied" else None,
                     approved_via=None if status != "applied" or not a["requires_approval"] else a["approved_via"])
            case["actions"].append(a)
            return a

        def add_message(fx_id: str):
            m = _remap(copy.deepcopy(fx_messages[fx_id]), ids)
            m["ts"] = iso(now())
            case["messages"].append(m)
            if m["direction"] == "out" and m["channel"] != "voice":
                outbound.send_message(store, {"case_id": case["case_id"], "user_id": uid, "channel": m["channel"],
                                              "kind": m["kind"], "text": m["text"], "expects_reply": m["kind"] == "alert",
                                              "action_id": None})

        for fx_step in T2["steps"]:
            await asyncio.sleep(_step_ms())
            data = _remap(copy.deepcopy(fx_step["data"]), ids)
            t, stage = fx_step["type"], fx_step["stage"]
            if t == "score":
                case["risk"], case["threat"], case["confidence"] = data["risk"], "coached", data["risk"]["confidence"]
            elif t == "verify":
                case["verification"] = data["verification"]
            elif t == "action":
                fx_id = next(k for k, v in ids.items() if v == data["action_id"])
                add_action(fx_id, "applied")
                if fx_actions[fx_id]["kind"] == "relock":
                    store.set_protection(uid, "port_out_protection", True)
                if fx_actions[fx_id]["kind"] == "hold_transfer_pin":
                    store.hold_transfer_pin(uid)
            elif t in ("message", "transcript"):
                add_message(next(k for k, v in ids.items() if v == data["message_id"]))
            elif t == "plan" and stage == "await":
                case["status"] = "awaiting_reply"
            elif t == "call":
                outbound.place_call(store, _remap(fixture("callreq.t2.json"), ids))
            elif t == "approval_needed":
                case["status"] = "recovering"
                for new in data["action_ids"]:
                    add_action(next(k for k, v in ids.items() if v == new), "awaiting_approval")
            elif t == "approved":
                for a in case["actions"]:
                    if a["action_id"] == data["action_id"]:
                        a.update(status="applied", approved_via="voice", applied_at=iso(now()))
                        if a["kind"] == "revoke_transfer_pin":
                            store.transfer_pins[uid] = {"status": "revoked", "hold_until": None}
            elif t == "summary":
                case["summary"] = data["summary"]
            elif t == "done":
                case["status"] = "watching"
                for a in case["actions"]:
                    if a["status"] == "awaiting_approval":
                        a["status"] = "rejected"
            store.add_step(case, run_id, fx_step["agent"], stage, t, fx_step["title"], data)
    finally:
        case["run_running"] = False


def heads_up(store: Store, case: dict):
    text = ("Titan: Heads up. The call you just answered says it's T-Mobile, but we can't verify it. "
            "We'll never ask for your PIN or ask you to turn off protection.")
    msg = {"message_id": new_id("msg"), "case_id": case["case_id"], "channel": "imessage", "direction": "out",
           "kind": "heads_up", "text": text, "ts": iso(now())}
    case["messages"].append(msg)
    store.add_step(case, new_id("run"), "messaging", "reach", "message", "Heads-up text sent: unverified call claiming to be T-Mobile",
                   {"message_id": msg["message_id"]})
    outbound.send_message(store, {"case_id": case["case_id"], "user_id": case["user_id"], "channel": "imessage",
                                  "kind": "heads_up", "text": text, "expects_reply": False, "action_id": None})
