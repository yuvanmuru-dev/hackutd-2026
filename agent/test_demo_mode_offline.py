"""DEMO_MODE test: record a run, then replay the same scenario with every model call failing.
Run: python test_demo_mode_offline.py (prints PASS). Uses a temp recording file; never touches the real one.
"""
import os
import tempfile
import time

REC = os.path.join(tempfile.mkdtemp(), "llm_cache.json")
os.environ.update(MOCK="0", LLM_CACHE="record", LLM_CACHE_PATH=REC, DEMO_MODE="0", DEMO_REPLAY_MAX_MS="0",
                  REPLY_TIMEOUT_S="0.3", RECOVERY_TIMEOUT_S="5", NVIDIA_API_KEY="test",
                  MESSAGING_URL="", VOICE_URL="", SAFETY_MODEL="", URLHAUS_AUTH_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
import test_workflow_offline as wf  # noqa: E402  (reuses the fake Nemotron; its own checks already ran on import)
from core import llm  # noqa: E402
from core.contracts import errors, fixture  # noqa: E402


def run_t2(c):
    c.post("/demo/reset")
    cid = c.post("/events", json=fixture("event.call_started.json") | {"event_id": f"evt_{time.time_ns()}"}).json()["case_id"]
    chk = c.post("/check", json=fixture("checkreq.protection_off.json") | {"customer_choice": "doing_it_myself"}).json()
    c.post("/protections/usr_maya/port_out_protection", json={"enabled": False, "via": "portal", "check_id": chk["check_id"]})
    c.post("/transfer-pin/usr_maya")
    d = wf.wait_status(c, cid, {"recovering"})
    for a in [a for a in d["actions"] if a["status"] == "awaiting_approval"]:
        c.post(f"/actions/{a['action_id']}/approve", json={"via": "voice"})
    return wf.wait_status(c, cid, {"watching"})


if os.path.exists(REC):
    os.remove(REC)  # start clean (importing test_workflow_offline ran its own checks first)
llm._cache = None
llm._stats.update(replayed=0, live=0, recorded=0)
llm.set_client(wf.FakeNemotron())
with TestClient(server.app) as c:
    first = run_t2(c)
    recorded = llm.cache_stats()
    assert recorded["recorded"] >= 5 and os.path.exists(REC), recorded

    # stage: models are down, DEMO_MODE replays everything from the recording
    os.environ.update(DEMO_MODE="1", LLM_CACHE="off")
    llm.set_client(wf.FakeNemotron(fail=True))
    llm._stats.update(replayed=0, live=0, recorded=0)
    second = run_t2(c)
    st = llm.cache_stats()
    assert st["replayed"] >= 5 and st["live"] == 0, st
    assert not [s for s in second["steps"] if s["type"] == "error" and "unavailable" in s["title"]], "no model fallbacks expected"
    assert any("Demo mode: replaying recorded Nemotron answers" in s["title"] for s in second["steps"])  # honest label
    assert second["threat"] == first["threat"] and second["summary"]["what_happened"] == first["summary"]["what_happened"]
    assert errors("CaseDetail", second) == []
    print(f"  recorded {recorded['recorded']} answers; replayed {st['replayed']} with the model down")
print("PASS")
