"""Evaluation protocol checks that prevent leakage and hidden fallback claims."""
import json
from pathlib import Path
import socket
import sys
import tempfile
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

    def test_separate_benign_controls_do_not_modify_split(self):
        before = run.file_hash(run.SPLIT)
        event = {"event_id": "evt_control_test", "user_id": "usr_maya",
                 "type": "message.forwarded", "ts": "2026-11-07T20:00:00Z",
                 "source": "generator", "data": {"channel": "sms", "text": "Your bill is ready in the app."}}
        wrapper = {"format_version": 1, "synthetic": True, "records": [
            {"text_id": "benign_test", "label": "legit", "event": event}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "benign_texts.json"
            path.write_text(json.dumps(wrapper))
            rows = run.load_benign(path)
            audit = {"network_attempts": 0, "write_attempts": 0, "scenario_read_attempts": 0}
            with run.offline_read_only(audit, (path,)):
                active, _, _ = run.evaluate({"test": list(rows)}, rows, audit)
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0]["trigger_type"], "message.forwarded")
            self.assertEqual(active[0]["label"], "legit")
            self.assertEqual(run.file_hash(run.SPLIT), before)
            with run.offline_read_only(audit, (path,)), self.assertRaises(RuntimeError):
                path.read_text()
        self.assertEqual(audit["scenario_read_attempts"], 1)

    def test_scorer_cannot_read_test_label_files(self):
        audit = {"network_attempts": 0, "write_attempts": 0}
        with run.offline_read_only(audit):
            with self.assertRaises(RuntimeError):
                (run.ROOT / "agent/packs/guard/data/scenarios/seed_code_relay_01.json").read_text()
        self.assertEqual(audit["scenario_read_attempts"], 1)

    def test_scorer_cannot_read_sealed_design_or_generator(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            for name in ("DESIGN.md", "generate.py", "manifest.json"):
                (directory / name).write_text("invented fixture, no real sealed content")
            audit = {"network_attempts": 0, "write_attempts": 0}
            with run.offline_read_only(audit, (directory,)):
                for path in directory.iterdir():
                    with self.assertRaises(RuntimeError):
                        path.read_text()
            self.assertEqual(audit["scenario_read_attempts"], 3)

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
        self.assertFalse(run.final_model_ready(status, active))

    def test_final_gate_rejects_partial_error_driven_model_run(self):
        good = {"prediction": {"model": "ml+rules"},
                "route": {"ml_called": True, "ml_error": None, "ml_returned_score": True}}
        bad = {"prediction": {"model": "rules"},
               "route": {"ml_called": True, "ml_error": "ValueError", "ml_returned_score": False}}
        status = {"module_present": True, "import_error": None}
        self.assertTrue(run.final_model_ready(status, [good]))
        self.assertFalse(run.final_model_ready(status, [good, bad]))
        empty_fallback = {"prediction": {"model": "rules"},
                          "route": {"ml_called": True, "ml_error": None, "ml_returned_score": False}}
        self.assertFalse(run.final_model_ready(status, [good, empty_fallback]))
        intentional_rules = {"prediction": {"model": "rules"},
                             "route": {"ml_called": True, "ml_error": None, "ml_returned_score": True}}
        self.assertTrue(run.final_model_ready(status, [good, intentional_rules]))

    def test_control_commit_must_contain_the_actual_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "controls.json"
            path.write_text("current data")
            root = str(path.parent.resolve())
            with patch.object(run.subprocess, "check_output", side_effect=[root, "abc123", b"old data"]):
                self.assertIsNone(run.committed_source(path))
            with patch.object(run.subprocess, "check_output", side_effect=[root, "abc123", b"current data"]):
                self.assertEqual(run.committed_source(path), "abc123")
            self.assertIsNone(run.committed_source(path))

    def test_test_informed_split_cannot_pass_independence_gate(self):
        audit = {"status": "test_informed", "affected_split_sha256": "old_split"}
        self.assertFalse(run.independent_split("old_split", audit))
        self.assertTrue(run.independent_split("new_sealed_split", audit))


if __name__ == "__main__":
    unittest.main()
