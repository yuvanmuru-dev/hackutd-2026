"""Evaluation protocol checks that prevent leakage and hidden fallback claims."""
import json
from pathlib import Path
import socket
import sys
import types
import unittest
from unittest.mock import patch

from evals import run


class ProtocolTests(unittest.TestCase):
    def test_replay_excludes_later_code_relay_login(self):
        path = run.ROOT / "agent/packs/guard/data/scenarios/seed_code_relay_01.json"
        scenario = json.loads(path.read_text())
        at = run.store_module.parse(next(e["ts"] for e in scenario["events"]
                                        if e["event_id"] == scenario["trigger_event_id"]))
        future = {e["event_id"] for e in scenario["events"] if run.store_module.parse(e["ts"]) > at}
        self.assertTrue(future)
        with run.frozen_clock(at):
            st, trigger, _ = run.replay(scenario)
            other, _, _ = run.replay(scenario)
            self.assertFalse(future & st.events.keys())
            self.assertEqual(trigger["type"], "otp.sent")
            self.assertNotIn("label", trigger)
            self.assertNotIn("variant", trigger)
            self.assertEqual(run.store_module.now(), at)
            call = st.active_call(scenario["user_id"])
            self.assertEqual(st.call_summary(call)["duration_s"], 8 * 60)
            st.events.clear()
            self.assertTrue(other.events)

    def test_offline_boundary_counts_even_caught_errors(self):
        audit = {"network_attempts": 0, "write_attempts": 0}
        with run.offline_read_only(audit):
            with self.assertRaises(RuntimeError):
                socket.getaddrinfo("example.com", 443)
            with self.assertRaises(RuntimeError):
                Path("unused-eval-test-file").write_text("no")
        self.assertEqual(audit, {"network_attempts": 1, "write_attempts": 1})
        self.assertFalse(Path("unused-eval-test-file").exists())

    def test_clock_restored(self):
        original = run.store_module.now
        at = run.datetime(2026, 11, 7, tzinfo=run.timezone.utc)
        with run.frozen_clock(at):
            self.assertEqual(run.store_module.now(), at)
        self.assertIs(run.store_module.now, original)

    def test_scorer_cannot_read_test_label_files(self):
        audit = {"network_attempts": 0, "write_attempts": 0}
        with run.offline_read_only(audit):
            with self.assertRaises(RuntimeError):
                (run.ROOT / "agent/packs/guard/data/scenarios/seed_code_relay_01.json").read_text()
        self.assertEqual(audit["scenario_read_attempts"], 1)

    def test_hidden_model_exception_is_recorded_as_rules_fallback(self):
        path = "agent/packs/guard/data/scenarios/seed_code_relay_01.json"
        scenario = json.loads((run.ROOT / path).read_text())
        module = types.ModuleType("packs.guard.ml")

        def broken_model(user_id, event, history):
            self.assertEqual(user_id, scenario["user_id"])
            self.assertNotIn("label", event)
            self.assertTrue(all("generator" not in e and "hard_negative" not in e for e in history))
            raise ValueError("intentional model failure")

        module.score = broken_model
        audit = {"network_attempts": 0, "write_attempts": 0}
        with patch.dict(sys.modules, {"packs.guard.ml": module}), run.offline_read_only(audit):
            active, _, status = run.evaluate({"test": [path]}, {path: scenario}, audit)
        self.assertTrue(status["module_present"])
        self.assertTrue(active[0]["route"]["ml_called"])
        self.assertEqual(active[0]["route"]["ml_error"], "ValueError")
        self.assertEqual(active[0]["prediction"]["model"], "rules")


if __name__ == "__main__":
    unittest.main()
