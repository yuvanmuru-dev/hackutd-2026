"""Tapping "I'm on a call: help me" makes Titan call right away (no 60 s wait for a text). Run: python test_help_call_offline.py"""
import os
import time

os.environ.update(MOCK="0", REPLY_TIMEOUT_S="60", RECOVERY_TIMEOUT_S="5", NVIDIA_API_KEY="test",
                  MESSAGING_URL="", VOICE_URL="", SAFETY_MODEL="", URLHAUS_AUTH_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
import test_workflow_offline as wf  # noqa: E402  (fake Nemotron)
from core import llm  # noqa: E402
from core.contracts import fixture  # noqa: E402
from core.store import iso, now  # noqa: E402

llm.set_client(wf.FakeNemotron())
with TestClient(server.app) as c:
    c.post("/demo/reset")
    server.store.outbox.clear()
    c.post("/events", json=fixture("event.call_started.json") | {"event_id": f"evt_{time.time_ns()}", "ts": iso(now())})
    t0 = time.time()
    res = c.post("/check", json=fixture("checkreq.protection_off.json") | {"customer_choice": "on_call_help"}).json()
    assert res["decision"] == "block" and res.get("case_id"), res
    call = None
    while time.time() - t0 < 20 and not call:
        call = next((r for r in server.store.outbox if r["kind"] == "call"), None)
        time.sleep(0.2)
    assert call, "Titan never called"
    took = time.time() - t0
    assert took < 15, f"call took {took:.1f}s (should not wait REPLY_TIMEOUT_S=60)"
    d = c.get(f"/cases/{res['case_id']}").json()
    assert any("asked for help" in s["title"] for s in d["steps"]), [s["title"] for s in d["steps"]]
    assert not any(s["title"].startswith("Waiting for") for s in d["steps"])
    print(f"  call placed {took:.1f}s after the help tap")
print("PASS")
