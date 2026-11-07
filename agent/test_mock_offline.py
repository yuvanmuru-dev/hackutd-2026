"""Offline test of the MOCK brain against contracts v0.3. Run: python test_mock_offline.py  (prints PASS)

Walks the T2 story (coached victim) through the real gate rules and the replayed run,
and validates every response against contracts/schema.json.
"""
import os
import time

os.environ["MOCK"] = "1"
os.environ["MOCK_STEP_MS"] = "5"
os.environ.pop("MESSAGING_URL", None)
os.environ.pop("VOICE_URL", None)

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
from core.contracts import errors, fixture  # noqa: E402


def ok(name, obj):
    errs = errors(name, obj)
    assert not errs, (name, errs[:3])
    return obj


def wait_case(c, cid, status, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        d = c.get(f"/cases/{cid}").json()
        if d["status"] == status:
            return d
        time.sleep(0.05)
    raise AssertionError(f"case {cid} never reached {status}: {d['status']}")


with TestClient(server.app) as c:
    c.post("/demo/reset")
    assert c.get("/health").json()["ok"]
    assert len(c.get("/tools").json()) >= 10
    for u in c.get("/users").json():
        ok("User", u)

    # contract violations are rejected
    bad = fixture("event.call_started.json") | {"type": "call.started", "data": {"attestation": "Z"}}
    assert c.post("/events", json=bad).status_code == 422

    # 1. scam call starts -> heads-up case
    r = c.post("/events", json=fixture("event.call_started.json")).json()
    assert r["trigger"] == "heads_up" and r["case_id"], r
    cid = r["case_id"]
    assert c.post("/events", json=fixture("event.call_started.json")).json()["duplicate"]
    ok("Timeline", c.get("/users/usr_maya/timeline").json())
    assert c.get("/protections/usr_maya").json()["shield_mode"] is True

    # 2. turning protection off during the call -> pause, and the portal can't skip the gate
    chk = ok("CheckResponse", c.post("/check", json=fixture("checkreq.protection_off.json")).json())
    assert chk["decision"] == "pause" and chk["pause_screen"], chk
    assert c.post("/protections/usr_maya/port_out_protection", json={"enabled": False, "via": "portal"}).status_code == 409
    chk2 = ok("CheckResponse", c.post("/check", json=fixture("checkreq.protection_off.json") | {"customer_choice": "doing_it_myself"}).json())
    assert chk2["decision"] == "allow", chk2
    st = ok("ProtectionState", c.post("/protections/usr_maya/port_out_protection",
                                      json={"enabled": False, "via": "portal", "check_id": chk2["check_id"]}).json())
    assert not next(p for p in st["protections"] if p["name"] == "port_out_protection")["enabled"]

    # 3. transfer PIN -> hold + run starts on the same case
    tp = c.post("/transfer-pin/usr_maya").json()
    ok("CheckResponse", tp["check"])
    assert tp["check"]["decision"] == "hold" and tp["check"]["case_id"] == cid, tp
    assert tp["protections"]["transfer_pin"]["status"] == "held"

    # 4. replay finishes; case matches the contract; Titan re-locked and kept the PIN unusable
    d = ok("CaseDetail", wait_case(c, cid, "watching"))
    assert d["threat"] == "coached" and d["summary"] and d["verification"], d["status"]
    assert d["steps"][-1]["type"] == "done"
    for s in d["steps"]:
        ok("StepEvent", s)
    kinds = {a["kind"]: a["status"] for a in d["actions"]}
    assert kinds["relock"] == "applied" and kinds["hold_transfer_pin"] == "applied", kinds
    st = c.get("/protections/usr_maya").json()
    assert next(p for p in st["protections"] if p["name"] == "port_out_protection")["enabled"]
    assert st["transfer_pin"]["status"] == "revoked"
    sent = [o for o in c.get("/demo/outbox").json()]
    assert any(o["kind"] == "call" for o in sent) and sum(o["kind"] == "send" for o in sent) >= 3
    for o in sent:
        ok("SendRequest" if o["kind"] == "send" else "CallRequest", o["payload"])

    # 5. SSE stream replays the whole run and ends on done
    body = c.get(f"/cases/{cid}/stream").text
    assert body.count("event: step") == len(d["steps"]) and '"type": "done"' in body

    # 6. doors post transcript lines; approvals work
    ok("Message", c.post(f"/cases/{cid}/events", json=fixture("caseevent.transcript.json")).json())
    a = c.post(f"/actions/{d['actions'][0]['action_id']}/approve", json={"via": "web"}).json()
    ok("Action", a)
    assert c.post("/actions/act_nope/approve", json={"via": "web"}).status_code == 404

    # 7. T3 (forwarded text) and T1 (takeover) scenarios via the console helper
    c.post("/demo/reset")
    c.post("/demo/play/t3")
    time.sleep(0.3)
    t3 = [x for x in c.get("/cases").json() if x["title"].startswith("Forwarded")][0]
    ok("CaseDetail", wait_case(c, t3["case_id"], "watching"))
    c.post("/demo/play/t1")
    time.sleep(2.5)
    t1 = [x for x in c.get("/cases").json() if x["title"].startswith("SIM swap")][0]
    assert ok("CaseDetail", wait_case(c, t1["case_id"], "watching"))["threat"] == "takeover"

    # 8. "help me" on the pause screen starts Titan immediately
    c.post("/demo/reset")
    c.post("/events", json=fixture("event.call_started.json"))
    h = ok("CheckResponse", c.post("/check", json=fixture("checkreq.protection_off.json") | {"customer_choice": "on_call_help"}).json())
    assert h["decision"] == "block" and h["case_id"]
    ok("CaseDetail", wait_case(c, h["case_id"], "watching"))

print("PASS")
