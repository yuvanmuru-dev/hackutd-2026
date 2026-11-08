"""Exercise watcher -> real brain routes with fixture replay and live delivery blocked."""
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

import dotenv

root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root / "agent"), str(root / "watcher")]
os.environ.update(MOCK="1", MOCK_STEP_MS="1", MESSAGING_URL="", VOICE_URL="",
                  NVIDIA_API_KEY="", SAFETY_MODEL="", URLHAUS_AUTH_KEY="")

with patch.object(dotenv, "load_dotenv", return_value=False), \
     patch("requests.sessions.Session.request", side_effect=RuntimeError("External HTTP blocked")), \
     patch("core.outbound._post") as delivery:
    import server
    import watcher
    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        class BrainBridge(watcher.Brain):
            def request(self, path, body=None):
                response = client.get(path) if body is None else client.post(path, json=body)
                response.raise_for_status()
                return response.json()

        brain = BrainBridge("http://isolated-brain")
        assert client.post("/demo/play/t2").status_code == 200
        deadline = time.monotonic() + 15
        while True:
            watches = brain.watches(datetime.now(timezone.utc))
            if watches:
                break
            assert time.monotonic() < deadline, "T2 did not produce an approved report and active watch"
            time.sleep(0.05)
        event = watcher.repeat_event(watches[0], "evt_watcher_brain_integration", datetime.now(timezone.utc))
        result = brain.post(event)
        assert result["trigger"] == "repeat_heads_up", result
        case = brain.request("/cases/" + result["case_id"])
        assert case["call"]["scam_label"] is True
        assert "reported as a scam" in case["messages"][-1]["text"]
        before = len(brain.request("/demo/outbox"))
        assert brain.post(event)["duplicate"] is True
        assert len(brain.request("/demo/outbox")) == before
        assert delivery.call_count == 0

print("PASS watcher -> brain: repeat labeled, heads-up authored, duplicate suppressed; 0 live deliveries")
