"""Freeze checks use a tiny temporary git repo, never a real model or sealed data."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from evals import freeze_model as freeze


class AfterDeadline(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 8, 7, tzinfo=timezone.utc)


class BeforeDeadline(AfterDeadline):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 8, 5, tzinfo=timezone.utc)


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(freeze, "ROOT", self.root)
        self.root_patch.start()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Evaluation fixture")
        self.write("agent/core/store.py", "# dummy source, never imported\n")
        self.write("contracts/schema.json", "{}\n")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture base")
        self.git("checkout", "-qb", "model")
        self.write("agent/packs/guard/ml/__init__.py", "# dummy source, never imported\n")
        self.write("agent/packs/guard/ml/models/risk.json", "{}\n")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture model")
        self.head = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "main")
        self.git("merge", "--no-ff", "-qm", "fixture merge", "model")
        self.merge = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.merge)

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def git(self, *args):
        env = {**os.environ, "GIT_AUTHOR_DATE": "2026-11-07T20:00:00Z",
               "GIT_COMMITTER_DATE": "2026-11-07T20:00:00Z"}
        return subprocess.check_output(["git", *args], cwd=self.root, text=True, env=env).strip()

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)

    def test_freeze_rejects_early_execution(self):
        with patch.object(freeze, "datetime", BeforeDeadline), self.assertRaisesRegex(ValueError, "window"):
            freeze.build_snapshot(self.merge, self.head)

    def test_snapshot_checks_model_hashes_and_runtime_drift(self):
        with patch.object(freeze, "datetime", AfterDeadline):
            snapshot = freeze.build_snapshot(self.merge, self.head)
            self.assertEqual(snapshot["model_commit"], self.merge)
            self.assertEqual(snapshot["model_head_commit"], self.head)
            self.assertEqual(snapshot["model_sha256"], freeze.aggregate(snapshot["model_hashes"]))
            self.write("agent/core/store.py", "# changed source\n")
            with self.assertRaisesRegex(ValueError, "Runtime differs"):
                freeze.verify_snapshot(snapshot)

    def test_untracked_serving_file_is_rejected(self):
        with patch.object(freeze, "datetime", AfterDeadline):
            snapshot = freeze.build_snapshot(self.merge, self.head)
            self.write("agent/packs/guard/ml/extra.py", "# untracked\n")
            with self.assertRaisesRegex(ValueError, "Unexpected serving"):
                freeze.verify_snapshot(snapshot)

    def test_merge_head_and_hash_map_cannot_be_substituted(self):
        with patch.object(freeze, "datetime", AfterDeadline):
            with self.assertRaisesRegex(ValueError, "second parent"):
                freeze.build_snapshot(self.merge, self.merge)
            snapshot = freeze.build_snapshot(self.merge, self.head)
            snapshot["model_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "aggregate"):
                freeze.verify_snapshot(snapshot)

    def test_freeze_file_is_exclusive(self):
        path = self.root / "frozen_model.json"
        freeze.write_freeze({"model_commit": "fixture"}, path)
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            freeze.write_freeze({"model_commit": "replacement"}, path)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(json.loads(before)["model_commit"], "fixture")

    def test_model_commit_after_tuning_cutoff_is_rejected(self):
        with patch.object(freeze, "datetime", AfterDeadline), \
                patch.object(freeze, "commit_time", return_value=AfterDeadline.now()):
            with self.assertRaisesRegex(ValueError, "after.*cutoff"):
                freeze.build_snapshot(self.merge, self.head)


if __name__ == "__main__":
    unittest.main()
