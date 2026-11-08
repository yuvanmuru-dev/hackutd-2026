"""Offline test of the optional face check (D-007). Run: python test_face_offline.py  (prints PASS)

FACE_ENABLED=1 for this test only. Checks: a passing face lets Maya continue and is logged on the case;
a failing face asks again; no face (camera denied) falls back to today's behavior; a passing face never
lifts the transfer-PIN hold during a suspicious call.
"""
import os

os.environ["MOCK"] = "1"
os.environ["MOCK_STEP_MS"] = "5"
os.environ["FACE_ENABLED"] = "1"
os.environ.update(MESSAGING_URL="", VOICE_URL="", SAFETY_MODEL="", URLHAUS_AUTH_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
from core.contracts import errors, fixture  # noqa: E402

GOOD = {"match": True, "similarity": 0.93, "liveness": 0.97, "antispoof": 0.95}
BAD = {"match": False, "similarity": 0.21, "liveness": 0.97, "antispoof": 0.95}


def check(c, extra):
    r = c.post("/check", json=fixture("checkreq.protection_off.json") | {"customer_choice": "doing_it_myself"} | extra).json()
    assert not errors("CheckResponse", r), errors("CheckResponse", r)[:3]
    return r


with TestClient(server.app) as c:
    c.post("/demo/reset")
    maya = next(u for u in c.get("/users").json() if u["user_id"] == "usr_maya")
    assert maya["face_enabled"] is True, maya
    cid = c.post("/events", json=fixture("event.call_started.json")).json()["case_id"]

    r = check(c, {"face": BAD})
    assert r["decision"] == "pause" and r["pause_screen"], r
    r = check(c, {})  # camera denied / library failed: today's behavior
    assert r["decision"] == "allow", r
    r = check(c, {"face": GOOD})
    assert r["decision"] == "allow" and "Face check passed on this device" in r["reasons"], r

    steps = [s for s in c.get(f"/cases/{cid}").json()["steps"] if s["data"].get("kind") == "face_check"]
    assert [s["title"] for s in steps] == ["Face check: no match 0.21 · live", "Face check: match 0.93 · live"], steps
    assert all(set(s["data"]) == {"kind", "on_device", "match", "similarity", "liveness", "antispoof"} for s in steps)

    # a passing face check proves it's Maya, not that nobody is coaching her: the PIN hold still applies
    r = c.post("/check", json={"user_id": "usr_maya", "action": "transfer_pin", "face": GOOD}).json()
    assert r["decision"] == "hold", r

print("PASS")
