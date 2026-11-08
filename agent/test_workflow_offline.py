"""Offline test of the REAL workflow (MOCK=0) with a fake Nemotron. Run: python test_workflow_offline.py (prints PASS)

Checks: Context -> Risk -> Verifier -> Response run and stream; the Verifier drops an unsupported claim; the outbound
guard blocks a link; Titan calls when there's no reply; approvals apply; summary sent; every output matches the
contract; and the run still finishes when every model call fails.
"""
import json
import os
import time

os.environ.update(MOCK="0", REPLY_TIMEOUT_S="0.3", RECOVERY_TIMEOUT_S="5", NVIDIA_API_KEY="test", SAFETY_MODEL="")
# Set (not pop): load_dotenv() never overrides an existing variable, so agent/.env can't re-enable real sends.
os.environ.update(MESSAGING_URL="", VOICE_URL="", SAFETY_MODEL="", URLHAUS_AUTH_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
from core import llm  # noqa: E402
from core.contracts import errors, fixture  # noqa: E402


class _Msg:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class FakeNemotron:
    """Answers each agent prompt with plausible JSON, including deliberate mistakes the guardrails must catch."""

    def __init__(self, fail=False):
        self.fail, self.calls = fail, []
        self.chat = type("C", (), {"completions": self})()

    def create(self, model, messages, **kw):
        sys_prompt, user = messages[0]["content"], messages[-1]["content"]
        self.calls.append(model)
        if self.fail:
            raise RuntimeError("model down")
        if isinstance(user, list):  # Nemotron VL reading a screenshot
            return type("R", (), {"choices": [_Msg("T-Mobile: your account is locked. Verify now at t-mobile-secure-help.co")]})()
        if "Decide which tools to call" in sys_prompt:
            out = {"plan": "Check the call, protections and account history", "tools": ["call_context", "policy_lookup", "not_a_tool"]}
        elif "Turn tool results into short facts" in sys_prompt:
            out = {"facts": [{"fact": "She is on an unverified call", "tool": "call_context"},
                             {"fact": "Port Out Protection was turned off during the call", "tool": "protection_status"}]}
        elif "You are the Risk agent" in sys_prompt:
            out = {"threat": "coached", "decision": "allow",  # too lenient on purpose: the rules floor must win
                   "assessment": "She appears to be coached by a caller posing as support.",
                   "claims": [{"claim": "Unverified call in progress", "tool": "call_context"},
                              {"claim": "Protection turned off during the call", "tool": "protection_status"},
                              {"claim": "She lost $5,000 yesterday", "tool": "bank_records"}]}  # unsupported: must be dropped
        elif "You are the Verifier" in sys_prompt:
            n = len(json.loads(user)["claims"])
            out = {"results": [{"index": i, "supported": True, "note": "in tool data"} for i in range(n)]}
        elif "Write what Titan says" in sys_prompt:
            out = {"alert_text": "Maya, please verify at https://t-mobile-help.co now. Reply YES or NO.",  # link: guard must block
                   "call_opening_line": "Hi Maya, this is Titan. I'll never ask you for a PIN or a code.",
                   "call_facts": ["The caller is not T-Mobile", "Port Out Protection is back on"]}
        elif "writing the incident summary" in sys_prompt:
            out = {"what_happened": "Someone on an unverified call asked you to turn off Port Out Protection.",
                   "why_we_stepped_in": "That is a common scam pattern.", "confidence_text": "We're fairly sure, not certain.",
                   "next_steps": ["Nothing else is needed."], "spot_it_next_time": "T-Mobile never asks you to turn off protection on a call."}
        elif "Classify the customer's reply" in sys_prompt:
            out = {"intent": "info", "shared": ["pin"], "note": "fake"}
        else:
            out = {}
        return type("R", (), {"choices": [_Msg("<think>hmm</think>```json\n" + json.dumps(out) + "\n```")]})()


def ok(name, obj):
    errs = errors(name, obj)
    assert not errs, (name, errs[:3])
    return obj


def wait_status(c, cid, statuses, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        d = c.get(f"/cases/{cid}").json()
        if d["status"] in statuses:
            return d
        time.sleep(0.05)
    raise AssertionError(f"{cid} stuck in {d['status']}; last step: {d['steps'][-1]['title'] if d['steps'] else None}")


def coached_flow(c):
    c.post("/demo/reset")
    cid = c.post("/events", json=fixture("event.call_started.json") | {"event_id": f"evt_{time.time_ns()}"}).json()["case_id"]
    chk = c.post("/check", json=fixture("checkreq.protection_off.json") | {"customer_choice": "doing_it_myself"}).json()
    c.post("/protections/usr_maya/port_out_protection", json={"enabled": False, "via": "portal", "check_id": chk["check_id"]})
    tp = c.post("/transfer-pin/usr_maya").json()
    assert tp["check"]["decision"] == "hold" and tp["check"]["case_id"] == cid, tp
    return cid


fake = FakeNemotron()
llm.set_client(fake)
with TestClient(server.app) as c:
    # ---- happy path with deliberate model mistakes
    cid = coached_flow(c)
    d = wait_status(c, cid, {"recovering"})          # no reply within REPLY_TIMEOUT_S -> Titan calls -> recovery
    agents_seen = [s["agent"] for s in d["steps"]]
    for a in ("context", "risk", "verifier", "response", "messaging"):
        assert a in agents_seen, (a, agents_seen)
    assert d["threat"] == "coached" and d["risk"]["model"] in ("rules", "ml+rules")  # ml+rules once Lane 2b's model lands (D-051)
    score_step = next(s for s in d["steps"] if s["type"] == "score")
    assert score_step["data"]["decision"] == "hold_and_alert", score_step   # rules floor beat the lenient model
    assert d["verification"]["claims_dropped"] >= 1, d["verification"]      # "$5,000 from bank_records" dropped
    import re as _re
    tappable = _re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(com|net|org|co|io)\b", _re.I)
    assert all(not tappable.search(m["text"]) for m in d["messages"] if m["direction"] == "out"), \
        [m["text"] for m in d["messages"] if m["direction"] == "out" and tappable.search(m["text"])]   # links defanged (D-012)
    kinds = {a["kind"]: a["status"] for a in d["actions"]}
    assert kinds.get("relock") == "applied" and kinds.get("hold_transfer_pin") == "applied", kinds
    st = c.get("/protections/usr_maya").json()
    assert next(p for p in st["protections"] if p["name"] == "port_out_protection")["enabled"]
    outbox = c.get("/demo/outbox").json()
    call = next(o for o in outbox if o["kind"] == "call")
    ok("CallRequest", call["payload"])
    # she answers on Titan's call: transcript line + approvals
    ok("Message", c.post(f"/cases/{cid}/events", json={"channel": "voice", "direction": "in", "kind": "transcript",
                                                         "text": "I told him my PIN.", "agent": "voice"}).json())
    pending = [a for a in c.get(f"/cases/{cid}").json()["actions"] if a["status"] == "awaiting_approval"]
    assert len(pending) >= 3, pending
    # D-054: spoken lines on Titan's call are audit-only, so a "yes" heard on the call approves nothing by itself
    c.post(f"/cases/{cid}/events", json={"channel": "voice", "direction": "in", "kind": "transcript", "text": "Yes, go ahead.", "agent": "voice"})
    c.post("/events", json={"event_id": f"evt_{time.time_ns()}", "user_id": "usr_maya", "type": "customer.reply", "ts": "2026-11-07T21:00:00Z",
                            "source": "voice", "call_id": None, "data": {"channel": "voice", "text": "yes", "case_id": cid}})
    time.sleep(0.3)
    still = [a for a in c.get(f"/cases/{cid}").json()["actions"] if a["status"] == "awaiting_approval"]
    assert len(still) == len(pending), "a spoken yes must not approve a recovery step (D-054)"
    # the brain texts recovery questions one at a time (D-042); a YES by text approves the step it asked about
    steps_sent = [o["payload"] for o in c.get("/demo/outbox").json() if o["kind"] == "send" and o["payload"]["kind"] == "recovery_step"]
    assert len(steps_sent) == 1 and steps_sent[0]["action_id"] == pending[0]["action_id"], steps_sent
    ev = {"event_id": f"evt_{time.time_ns()}", "user_id": "usr_maya", "type": "customer.reply", "ts": "2026-11-07T21:00:00Z",
          "source": "messaging", "call_id": None, "data": {"channel": "imessage", "text": "YES", "case_id": cid}}
    assert c.post("/events", json=ev).json()["accepted"]
    for _ in range(100):
        acts = {a["action_id"]: a for a in c.get(f"/cases/{cid}").json()["actions"]}
        if acts[pending[0]["action_id"]]["status"] == "applied":
            break
        time.sleep(0.05)
    assert acts[pending[0]["action_id"]]["status"] == "applied" and acts[pending[0]["action_id"]]["approved_via"] == "sms"
    time.sleep(0.2)
    steps_sent = [o["payload"] for o in c.get("/demo/outbox").json() if o["kind"] == "send" and o["payload"]["kind"] == "recovery_step"]
    assert len(steps_sent) == 2 and steps_sent[1]["action_id"] == pending[1]["action_id"], steps_sent
    pending = pending[1:]
    for a in pending[:-1]:
        ok("Action", c.post(f"/actions/{a['action_id']}/approve", json={"via": "voice"}).json())
    c.post(f"/actions/{pending[-1]['action_id']}/reject", json={"via": "voice"})
    d = ok("CaseDetail", wait_status(c, cid, {"watching"}))
    assert d["steps"][-1]["type"] == "done"
    assert d["summary"] and d["summary"]["you_approved"], d["summary"]
    assert any(m["kind"] == "summary" for m in d["messages"])
    assert c.get("/protections/usr_maya").json()["transfer_pin"]["status"] == "revoked"
    for o in c.get("/demo/outbox").json():
        ok("SendRequest" if o["kind"] == "send" else "CallRequest", o["payload"])
    print(f"  coached run: {len(d['steps'])} steps, {len(fake.calls)} model calls, models {sorted(set(fake.calls))}")

    # ---- scam text
    c.post("/demo/reset")
    c.post("/demo/play/t3")
    time.sleep(0.3)
    t3 = next(x for x in c.get("/cases").json() if x["title"].startswith("Forwarded"))
    d3 = ok("CaseDetail", wait_status(c, t3["case_id"], {"watching"}))
    assert d3["threat"] == "scam_text" and any(m["direction"] == "out" for m in d3["messages"])
    outs = [m["text"] for m in d3["messages"] if m["direction"] == "out"]
    assert all(not tappable.search(t) for t in outs), outs
    assert any("[.]" in t for t in outs), outs   # the scam domain is named, safely

    # ---- screenshot forwarded: Nemotron VL reads it, then the scam-text check runs on the text (D-047)
    c.post("/demo/reset")
    shot = {"event_id": f"evt_{time.time_ns()}", "user_id": "usr_maya", "type": "message.forwarded", "ts": "2026-11-07T21:00:00Z",
            "source": "messaging", "call_id": None, "data": {"channel": "imessage", "image_url": "data:image/png;base64,iVBORw0KGgo="}}
    cid_s = c.post("/events", json=shot).json()["case_id"]
    ds = ok("CaseDetail", wait_status(c, cid_s, {"watching"}))
    assert any(st["title"].startswith("Read from screenshot") for st in ds["steps"]), [st["title"] for st in ds["steps"]]
    assert ds["threat"] == "scam_text" and any("[.]" in m["text"] for m in ds["messages"] if m["direction"] == "out")
    assert any("Nemotron VL" in x for x in ds["data_used"])
    assert any("vl" in m for m in fake.calls), fake.calls

    # ---- resilience: every model call fails -> deterministic fallbacks, run still completes
    llm.set_client(FakeNemotron(fail=True))
    import core.llm as L
    L.time.sleep = lambda s: None  # skip retry backoff in the test
    cid = coached_flow(c)
    d = wait_status(c, cid, {"recovering"})
    assert any(s["type"] == "error" for s in d["steps"]) and d["threat"] == "coached"
    for a in [a for a in d["actions"] if a["status"] == "awaiting_approval"]:
        c.post(f"/actions/{a['action_id']}/approve", json={"via": "voice"})
    d = ok("CaseDetail", wait_status(c, cid, {"watching"}))
    assert d["summary"] and d["steps"][-1]["type"] == "done"

print("PASS")
