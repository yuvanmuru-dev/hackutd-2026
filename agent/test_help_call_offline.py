"""Tapping "I'm on a call: help me" makes Titan call right away (no 60 s wait for a text), analyzes the attempted
protection change (not her newest portal login/behavior event), and calls even if the verdict is "legit".
Run: python test_help_call_offline.py"""
import os
import time

os.environ.update(MOCK="0", REPLY_TIMEOUT_S="60", RECOVERY_TIMEOUT_S="5", NVIDIA_API_KEY="test",
                  MESSAGING_URL="", VOICE_URL="", SAFETY_MODEL="", URLHAUS_AUTH_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
import test_workflow_offline as wf  # noqa: E402  (fake Nemotron)
from core import llm, workflow  # noqa: E402
from core.contracts import fixture  # noqa: E402
from core.store import iso, now  # noqa: E402

llm.set_client(wf.FakeNemotron())


def ev(name, **over):
    return fixture(name) | {"event_id": f"evt_{time.time_ns()}", "ts": iso(now())} | over


def help_run(c):
    c.post("/demo/reset")
    server.store.outbox.clear()
    c.post("/events", json=ev("event.call_started.json"))
    # what the real portal sends during the call before she taps help (Karthik's run): sign-in + behavior summary
    c.post("/events", json=ev("event.login.json") | {"call_id": None})
    c.post("/events", json=ev("event.portal_signals.json") | {"call_id": None})
    t0 = time.time()
    res = c.post("/check", json=fixture("checkreq.protection_off.json") | {"customer_choice": "on_call_help"}).json()
    assert res["decision"] == "block" and res.get("case_id"), res
    call = None
    while time.time() - t0 < 20 and not call:
        call = next((r for r in server.store.outbox if r["kind"] == "call"), None)
        time.sleep(0.2)
    d = c.get(f"/cases/{res['case_id']}").json()
    return call, time.time() - t0, d


with TestClient(server.app) as c:
    call, took, d = help_run(c)
    assert call, ("Titan never called", [s["title"] for s in d["steps"]])
    assert took < 15, f"call took {took:.1f}s (should not wait REPLY_TIMEOUT_S=60)"
    assert d["threat"] != "legit", (d["threat"], [s["title"] for s in d["steps"]])  # analyzed the protection-off attempt
    assert any("asked for help" in s["title"] for s in d["steps"]), [s["title"] for s in d["steps"]]
    assert not any(s["title"].startswith("Waiting for") for s in d["steps"])
    print(f"  call placed {took:.1f}s after the help tap · threat {d['threat']}")

    # even if every signal looks ordinary, an explicit help request still gets a call (no invented scam verdict)
    real_risk = workflow.Run.risk

    async def legit_risk(self):
        await real_risk(self)
        self.case["threat"], self.decision = "legit", "allow"
    workflow.Run.risk = legit_risk
    try:
        call, took, d = help_run(c)
    finally:
        workflow.Run.risk = real_risk
    assert call, ("legit verdict: Titan never called", [s["title"] for s in d["steps"]])
    assert d["threat"] == "legit" and any("she asked for help: calling her" in s["title"] for s in d["steps"])
    print(f"  legit verdict still called after {took:.1f}s")
print("PASS")
