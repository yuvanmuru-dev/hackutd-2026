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
with patch.object(dotenv, "load_dotenv", return_value=False), patch("requests.post") as outbound:
    outbound.side_effect = RuntimeError("Offline tests must not make outbound HTTP requests")
    runpy.run_path(str(agent / "test_workflow_offline.py"), run_name="__main__")
    assert outbound.call_count == 0, "Offline workflow attempted an outbound HTTP request"

print("PASS offline isolation: 0 outbound HTTP requests")
