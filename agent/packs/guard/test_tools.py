"""Offline checks for sourced, read-only guard tools.

Run from the repo root:
    PYTHONPATH=agent python3 -m unittest packs.guard.test_tools
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.contracts import errors, fixture
from core.events import ingest
from core.store import Store
from packs.guard import tools


def snapshot(store: Store) -> dict:
    """Store's lock cannot be copied; every data field can."""
    return copy.deepcopy({key: value for key, value in vars(store).items() if key != "lock"})


class GuardToolsTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        history = tempfile.TemporaryDirectory()
        self.addCleanup(history.cleanup)
        history_patch = patch.object(tools, "HISTORY_DIR", Path(history.name))
        history_patch.start()
        self.addCleanup(history_patch.stop)
        env_patch = patch.dict(os.environ, {"MOCK": "1"}, clear=True)
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def add_event(self, event_id: str, kind: str, ts: str, data: dict,
                  user_id: str = "usr_maya") -> None:
        self.store.events[event_id] = {
            "event_id": event_id, "user_id": user_id, "type": kind,
            "ts": ts, "source": "generator", "data": data,
        }

    def login(self, event_id: str, region: str, ts: str,
              user_id: str = "usr_maya", succeeded: bool = True) -> None:
        self.add_event(event_id, "login", ts,
                       {"region": region, "device_hash": "h_test_device",
                        "new_device": False, "succeeded": succeeded}, user_id)

    def test_traveler_compares_current_line_region(self):
        self.login("evt_travel_login", "Denver, CO", "2026-11-07T20:00:00Z", "usr_marcus")
        self.add_event("evt_travel_line", "line.region", "2026-11-07T20:01:00Z",
                       {"region": "Denver, CO"}, "usr_marcus")
        before = snapshot(self.store)
        output = tools.location_match(self.store, user_id="usr_marcus")
        self.assertIs(output["result"]["match"], True)
        self.assertEqual(output["result"]["line_region"], "Denver, CO")
        self.assertEqual(output["source"]["record"], "events/evt_travel_line")
        self.assertEqual(snapshot(self.store), before)

    def test_remote_request_and_failed_login_can_mismatch(self):
        self.login("evt_request", "Phoenix, AZ", "2026-11-07T20:00:00Z", succeeded=False)
        self.add_event("evt_line", "line.region", "2026-11-07T20:01:00Z",
                       {"region": "Dallas, TX"})
        output = tools.location_match(self.store, user_id="usr_maya")
        self.assertIs(output["result"]["match"], False)
        self.assertEqual(output["result"]["request_region"], "Phoenix, AZ")

    def test_missing_signal_is_unverifiable(self):
        for kind in (None, "login", "line.region"):
            with self.subTest(kind=kind):
                self.store.events.clear()
                if kind == "login":
                    self.login("evt_login", "Dallas, TX", "2026-11-07T20:00:00Z")
                elif kind:
                    self.add_event("evt_line", kind, "2026-11-07T20:00:00Z", {"region": "Dallas, TX"})
                output = tools.location_match(self.store, user_id="usr_maya")
                self.assertIsNone(output["result"]["match"])
                self.assertEqual(output["summary"], "Line location unknown (unverifiable)")

    def test_target_event_prevents_future_snapshot_leakage(self):
        self.login("evt_old_login", "Dallas, TX", "2026-11-07T14:00:00-06:00")
        self.add_event("evt_old_line", "line.region", "2026-11-07T20:01:00Z", {"region": "Dallas, TX"})
        self.add_event("evt_trigger", "transfer_pin.requested", "2026-11-07T20:02:00Z", {})
        self.login("evt_new_login", "Phoenix, AZ", "2026-11-07T20:03:00Z")
        self.add_event("evt_new_line", "line.region", "2026-11-07T20:04:00Z", {"region": "Houston, TX"})
        before = tools.location_match(self.store, user_id="usr_maya", event_id="evt_trigger")
        latest = tools.location_match(self.store, user_id="usr_maya")
        self.assertIs(before["result"]["match"], True)
        self.assertEqual(before["result"]["request_region"], "Dallas, TX")
        self.assertIs(latest["result"]["match"], False)
        unknown = tools.location_match(self.store, user_id="usr_maya", event_id="evt_missing")
        self.assertIsNone(unknown["result"]["match"])

    def test_expired_hold_is_derived_without_state_transition(self):
        expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        self.store.transfer_pins["usr_maya"] = {"status": "held", "hold_until": expired}
        before = snapshot(self.store)
        output = tools.protection_status(self.store, user_id="usr_maya")
        self.assertEqual(output["result"]["state"]["transfer_pin"], {"status": "active", "hold_until": None})
        self.assertEqual(snapshot(self.store), before)

    def test_t2_mock_call_uses_trigger_time(self):
        for event in fixture("scenario.t2.json")["events"]:
            ingest(self.store, copy.deepcopy(event))
        before = snapshot(self.store)
        output = tools.call_context(self.store, user_id="usr_maya")
        self.assertEqual(output["result"]["minutes"], 19)
        self.assertIs(output["result"]["suspicious"], True)
        self.assertIn("transfer_pin.requested", output["result"]["actions_during_call"])
        self.assertEqual(snapshot(self.store), before)

    def test_persona_baselines_are_minimized(self):
        account = tools.account_history(self.store, user_id="usr_maya")["result"]
        device = tools.device_sim_status(self.store, user_id="usr_maya")["result"]
        self.assertEqual(account["known_device_count"], 2)
        self.assertEqual(account["login_frequency_bucket"], "monthly")
        self.assertEqual(device["device_age_bucket"], "4y_plus")
        self.assertNotIn("known_device_hashes", account)
        self.assertNotIn("devices_seen", account)
        self.assertNotIn("last_login_device", device)

    def test_nine_tools_and_sources_leave_store_unchanged(self):
        schema_names = {schema["function"]["name"] for schema in tools.TOOL_SCHEMAS}
        self.assertEqual(schema_names, set(tools.TOOLS))
        self.assertEqual(len(schema_names), 9)
        before = snapshot(self.store)
        for name, fn in tools.TOOLS.items():
            kwargs = ({"text": "A text forwarded for checking"} if name == "check_message"
                      else {"question": "verification code"} if name == "policy_lookup"
                      else {"number_hash": "h_unreported"} if name == "recent_scam_reports"
                      else {"user_id": "usr_maya"})
            with self.subTest(tool=name):
                output = fn(self.store, **kwargs)
                self.assertEqual(set(output), {"summary", "result", "source"})
                self.assertIsInstance(output["summary"], str)
                self.assertNotIn("\n", output["summary"])
                self.assertEqual(errors("Source", output["source"]), [])
                json.dumps(output)
        self.assertEqual(snapshot(self.store), before)


if __name__ == "__main__":
    unittest.main()
