"""Run Lane 1's unchanged offline assertions without live .env or outbound HTTP.

From agent/: uv run --no-project --with-requirements requirements.txt python ../messaging/scripts/test-brain-offline.py
"""
import os
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

import dotenv

agent = Path(__file__).resolve().parents[2] / "agent"
sys.path.insert(0, str(agent))
os.environ.pop("MESSAGING_URL", None)
os.environ.pop("VOICE_URL", None)

# Older python-dotenv versions have no PYTHON_DOTENV_DISABLED support. The
# workflow test supplies its own fake model and test configuration; reloading
# the developer's live .env would re-enable the door URLs it explicitly removes.
with patch.object(dotenv, "load_dotenv", return_value=False), \
     patch("requests.sessions.Session.request") as network, \
     patch("core.outbound._post") as delivery:
    network.side_effect = RuntimeError("External HTTP is blocked during offline tests")
    delivery.side_effect = AssertionError("Offline tests must not dispatch to a live door")
    runpy.run_path(str(agent / "test_workflow_offline.py"), run_name="__main__")
    assert delivery.call_count == 0, "Offline workflow attempted a live message/call delivery"

print(f"PASS offline isolation: 0 live deliveries; {network.call_count} external HTTP attempts blocked")
