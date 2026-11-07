"""Offline test of the API with a fake model. Run: python test_server_offline.py  (prints PASS)"""
from fastapi.testclient import TestClient
import server, test_loop_offline as t  # reuses the fake model + fake tools

server._client = t.FakeClient()
c = TestClient(server.app)
assert c.get("/health").json()["ok"]
assert len(c.get("/tools").json()) == 4
r = c.post("/check", json={"address": "x", "listing": "Not in a flood zone.", "channel": "email"}).json()
assert r["channel"] == "email" and r["claims"][0]["verdict"] == "supported", r
assert c.post("/tools/nope", json={}).status_code == 404
print("PASS")
