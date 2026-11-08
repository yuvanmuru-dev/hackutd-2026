"""Single-attempt protocol tests. Only invented fixtures are scored here."""
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from evals import sealed


def fake_prediction():
    return {"scenario_id": "fixture_benign", "label": "legit", "hard_negative": True,
            "variant": "fixture_family", "trigger_type": "message.forwarded",
            "prediction": {"threat": "legit", "model": "fixture_model", "confidence": "low",
                           "probability": 0.1, "calibrated": False},
            "route": {"ml_called": True, "ml_error": None, "ml_returned_score": True}}


class SealedTests(unittest.TestCase):
    def test_exclusive_receipt_preserves_first_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "attempt/receipt.json"
            sealed.claim_attempt(path, {"dataset_sha256": "fixture"})
            first = path.read_bytes()
            with self.assertRaises(FileExistsError):
                sealed.claim_attempt(path, {"dataset_sha256": "replacement"})
            self.assertEqual(path.read_bytes(), first)

    def make_fixture(self, folder, fail=False):
        root = Path(folder)
        data = root / "data"
        data.mkdir()
        for name in ("manifest.json", "scenarios.jsonl", "DESIGN.md", "generate.py"):
            (data / name).write_text("fixture bytes, never a real sealed record")
        freeze = root / "freeze.json"
        freeze.write_text(json.dumps({"model_commit": "fixture_merge", "model_head_commit": "fixture_head",
                                     "model_sha256": "fixture_model_hash"}))
        args = types.SimpleNamespace(freeze=freeze, sealed_manifest=data / "manifest.json")
        runner = types.SimpleNamespace(OUT=root, committed_source=lambda _: "fixture_data_commit",
            git=lambda *args: "fixture_evaluator" if args[0] == "rev-parse" else "",
            hashes=lambda _: {}, offline_read_only=lambda *_: nullcontext(),
            final_model_ready=lambda *_: True, percent=lambda x: "N/A" if x is None else f"{x:.1%}")
        calls = []

        def evaluate(split, rows, audit, outputs):
            receipt = root / "attempt/receipt.json"
            self.assertEqual(json.loads(receipt.read_text())["status"], "started")
            calls.append(True)
            outputs[0].append(fake_prediction())
            outputs[1].append(fake_prediction())
            if fail:
                raise ValueError("fixture interrupted after first prediction")
            return outputs[0], outputs[1], {"module_present": True, "import_error": None}

        runner.evaluate = evaluate
        manifest = {"dataset_file": "scenarios.jsonl", "dataset_sha256": "fixture_data_hash",
                    "benign_scenario_ids": ["fixture_benign"]}
        return root, args, runner, calls, manifest

    def test_successful_attempt_scores_once_and_rejects_second(self):
        with tempfile.TemporaryDirectory() as folder:
            root, args, runner, calls, manifest = self.make_fixture(folder)
            with patch.object(sealed, "ATTEMPT", root / "attempt"), \
                    patch.object(sealed.freeze_model, "verify_snapshot"), \
                    patch.object(sealed, "load_data", return_value=(manifest, {"fixture_benign": {}})), \
                    patch("builtins.print"):
                sealed.execute(args, runner)
                with self.assertRaisesRegex(RuntimeError, "consumed"):
                    sealed.execute(args, runner)
            self.assertEqual(len(calls), 1)
            result = json.loads((root / "attempt/results.json").read_text())
            self.assertTrue(result["provenance"]["headline_eligible"])
            self.assertEqual(result["benign_texts"]["brain"]["support"], 1)

    def test_failure_preserves_partial_outputs_and_consumes_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root, args, runner, calls, manifest = self.make_fixture(folder, fail=True)
            with patch.object(sealed, "ATTEMPT", root / "attempt"), \
                    patch.object(sealed.freeze_model, "verify_snapshot"), \
                    patch.object(sealed, "load_data", return_value=(manifest, {"fixture_benign": {}})):
                with self.assertRaisesRegex(ValueError, "interrupted"):
                    sealed.execute(args, runner)
                with self.assertRaisesRegex(RuntimeError, "consumed"):
                    sealed.execute(args, runner)
            self.assertEqual(len(calls), 1)
            self.assertEqual(json.loads((root / "attempt/receipt.json").read_text())["status"], "failed")
            self.assertEqual(len(json.loads((root / "attempt/failure.json").read_text())["predictions"]), 1)
            self.assertIn("No headline numbers", (root / "attempt/results.md").read_text())


if __name__ == "__main__":
    unittest.main()
