"""Offline test of the typing-rhythm signal. Run: python test_rhythm_offline.py  (prints PASS)

The portal sends typing_rhythm_distance (timing only, D-006). The brain shows it in the portal_signals
summary the Context agent and dashboards see, and never lets it change the risk score (D-053).
"""
import os

os.environ["MOCK"] = "1"
os.environ["MOCK_STEP_MS"] = "5"
os.environ.update(MESSAGING_URL="", VOICE_URL="", SAFETY_MODEL="", URLHAUS_AUTH_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
from core import toolbox  # noqa: E402
from core.contracts import errors, fixture  # noqa: E402
from core.store import store  # noqa: E402

N = 0


def post_signals(c, rhythm):
    global N
    N += 1
    ev = fixture("event.portal_signals.json")
    ev["event_id"] = f"evt_rhythm_{N}"
    ev["ts"] = f"2026-11-07T20:3{N}:10Z"
    ev["data"]["typing_rhythm_distance"] = rhythm
    assert not errors("Event", ev), errors("Event", ev)[:3]
    r = c.post("/events", json=ev)
    assert r.status_code < 300, r.text
    real = toolbox.run_tool(store, "portal_signals", {"user_id": "usr_maya"})  # what the workflow's Context agent runs
    placeholder = toolbox.portal_signals(store, "usr_maya")
    assert real["summary"].split(" · ")[3:] == placeholder["summary"].split(" · ")[3:], (real, placeholder)
    return real


with TestClient(server.app) as c:
    c.post("/demo/reset")
    c.post("/events", json=fixture("event.call_started.json"))
    trigger = fixture("event.call_started.json")

    out = post_signals(c, 2.8)
    assert "typing rhythm 2.8× off her usual" in out["summary"], out["summary"]
    assert out["result"]["typing_rhythm_distance"] == 2.8
    score_off = toolbox.rules_score(store, "usr_maya", trigger)

    out = post_signals(c, 0.4)
    assert "typing matches her usual rhythm" in out["summary"], out["summary"]

    out = post_signals(c, None)
    assert "rhythm" not in out["summary"], out["summary"]
    score_null = toolbox.rules_score(store, "usr_maya", trigger)

    # Not a scoring input: same rules score with or without the rhythm.
    assert score_off == score_null, (score_off, score_null)

print("PASS")
