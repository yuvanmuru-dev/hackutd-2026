"""D-062 text commands (STATUS / LOCK / HELP). Run: python test_commands_offline.py (prints PASS). No network."""
import os
import time

os.environ.update(MOCK="0", MESSAGING_URL="", VOICE_URL="", NVIDIA_API_KEY="test", SAFETY_MODEL="", URLHAUS_AUTH_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
from core import commands  # noqa: E402
from core.contracts import errors  # noqa: E402


def text(c, body, case_id=None, typ=None):
    data = {"channel": "imessage", "text": body} | ({"case_id": case_id} if case_id else {})
    ev = {"event_id": f"evt_{time.time_ns()}", "user_id": "usr_maya", "type": typ or ("customer.reply" if case_id else "message.forwarded"),
          "ts": "2026-11-08T13:00:00Z", "source": "messaging", "call_id": None, "data": data}
    return c.post("/events", json=ev).json()


def prot(c):
    return {p["name"]: p["enabled"] for p in c.get("/protections/usr_maya").json()["protections"]}


assert commands.match({"type": "message.forwarded", "data": {"channel": "imessage", "text": " lock! "}}) == "LOCK"
for not_cmd in ("lock my account", "I told him my PIN", "YES", "unlock", "status?? http://x.co"):
    assert commands.match({"type": "message.forwarded", "data": {"channel": "imessage", "text": not_cmd}}) is None, not_cmd
assert commands.match({"type": "customer.reply", "data": {"channel": "voice", "text": "LOCK"}}) is None  # spoken lines never act (D-054)

with TestClient(server.app) as c:
    c.post("/demo/reset")
    c.post("/protections/usr_maya/port_out_protection", json={"enabled": False, "via": "portal"})
    assert prot(c)["port_out_protection"] is False

    r = text(c, "STATUS")
    assert r["trigger"] is None and r["case_id"], r
    d = c.get(f"/cases/{r['case_id']}").json()
    reply = [m for m in d["messages"] if m["direction"] == "out"][-1]["text"]
    assert "Port Out Protection: OFF" in reply and "LOCK" in reply, reply

    r2 = text(c, "Lock", case_id=r["case_id"])
    assert r2["case_id"] == r["case_id"]
    assert all(prot(c).values()), prot(c)  # every protection on
    d = c.get(f"/cases/{r['case_id']}").json()
    assert any(s["title"].startswith("Turned Port Out Protection on") for s in d["steps"]), [s["title"] for s in d["steps"]]
    assert any(e["type"] == "protection.changed" and e["data"]["enabled"] and e["source"] == "messaging" for e in d["timeline"])
    assert [m["text"] for m in d["messages"] if m["direction"] == "in"] == ["STATUS", "Lock"]
    assert "Locked" in d["messages"][-1]["text"] and "never a text" in d["messages"][-1]["text"]
    assert errors("CaseDetail", d) == [], errors("CaseDetail", d)

    assert "Everything was already locked" in c.get(f"/cases/{text(c, 'LOCK')['case_id']}").json()["messages"][-1]["text"]
    assert "STATUS" in c.get(f"/cases/{text(c, 'help')['case_id']}").json()["messages"][-1]["text"]

    # a real forwarded scam text still starts the scam_text run
    r3 = text(c, "Your T-Mobile account is locked, verify now at t-mobile-secure-help.co")
    assert r3["trigger"] == "scam_text", r3
print("PASS")
