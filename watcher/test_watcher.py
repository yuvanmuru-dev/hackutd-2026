import copy
from datetime import timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import watcher


CASE = json.loads((watcher.ROOT / "contracts/fixtures/case.t2.json").read_text())
NOW = watcher.instant("2026-11-07T22:00:00Z")


class FakeBrain:
    def __init__(self, watches):
        self.active = watches
        self.posts = []
        self.fail = False

    def watches(self, _now):
        return self.active

    def post(self, event):
        self.posts.append(event)
        if self.fail:
            self.fail = False
            raise TimeoutError("Response lost after acceptance")
        return {"accepted": True}


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.case = copy.deepcopy(CASE)
        self.watch = watcher.active_watch(self.case, NOW)
        self.assertIsNotNone(self.watch)

    def test_watch_requires_applied_report_and_unexpired_explicit_watch(self):
        self.assertEqual(self.watch.number_hash, "h_8f2c19")
        self.assertIsNone(watcher.active_watch(self.case, self.watch.until))
        for action in self.case["actions"]:
            if action["kind"] == "report_number":
                action["status"] = "rejected"
        self.assertIsNone(watcher.active_watch(self.case, NOW))
        self.case = copy.deepcopy(CASE)
        self.case["steps"] = [s for s in self.case["steps"] if s["stage"] != "watch"]
        self.assertIsNone(watcher.active_watch(self.case, NOW))

    def test_repeated_call_matches_user_hash_and_watch_window(self):
        event = watcher.repeat_event(self.watch, "evt_repeat_1", NOW)
        watcher.validate("Event", event)
        self.assertTrue(watcher.matches(event, [self.watch], NOW))
        self.assertEqual(event["source"], "watcher")
        self.assertFalse(event["data"]["scam_label"], "Only the brain labels a reported number")
        changed = copy.deepcopy(event)
        changed["data"]["other_number_hash"] = "h_other"
        self.assertFalse(watcher.matches(changed, [self.watch], NOW))
        changed = copy.deepcopy(event)
        changed["user_id"] = "usr_dev"
        self.assertFalse(watcher.matches(changed, [self.watch], NOW))
        changed = copy.deepcopy(event)
        changed["ts"] = (self.watch.start - timedelta(seconds=1)).isoformat()
        self.assertFalse(watcher.matches(changed, [self.watch], NOW))
        event["data"]["direction"] = "out"
        self.assertFalse(watcher.matches(event, [self.watch], NOW))

    def test_polling_and_restart_post_once_with_metadata_only_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            calls, state = Path(directory) / "calls.jsonl", Path(directory) / "checkpoint.json"
            event = watcher.repeat_event(self.watch, "evt_repeat_2", NOW)
            calls.write_text(json.dumps(event) + "\n" + json.dumps(event) + "\n")
            brain = FakeBrain([self.watch])
            queue = watcher.Queue(calls, state)
            self.assertEqual(queue.once(brain, NOW), 1)
            self.assertEqual(queue.once(brain, NOW), 0)
            self.assertEqual(watcher.Queue(calls, state).once(brain, NOW), 0)
            self.assertEqual(len(brain.posts), 1)
            self.assertNotIn(self.watch.number_hash, state.read_text())
            self.assertNotIn("caller_name", state.read_text())

    def test_response_loss_retries_same_event_id_without_advancing_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            calls, state = Path(directory) / "calls.jsonl", Path(directory) / "checkpoint.json"
            event = watcher.repeat_event(self.watch, "evt_repeat_3", NOW)
            calls.write_text(json.dumps(event) + "\n")
            brain = FakeBrain([self.watch])
            brain.fail = True
            queue = watcher.Queue(calls, state)
            with self.assertRaises(TimeoutError):
                queue.once(brain, NOW)
            self.assertFalse(state.exists())
            self.assertEqual(queue.once(brain, NOW), 1)
            self.assertEqual(brain.posts[0], brain.posts[1])

    def test_nonmatching_calls_and_absent_feed_send_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            calls, state = Path(directory) / "calls.jsonl", Path(directory) / "checkpoint.json"
            brain = FakeBrain([self.watch])
            queue = watcher.Queue(calls, state)
            self.assertEqual(queue.once(brain, NOW), 0)
            event = watcher.repeat_event(self.watch, "evt_repeat_4", NOW)
            event["data"]["other_number_hash"] = "h_unreported"
            calls.write_text(json.dumps(event) + "\n")
            self.assertEqual(queue.once(brain, NOW), 0)
            self.assertEqual(brain.posts, [])

    def test_brain_transport_posts_contract_event_and_accepts_duplicate_ack(self):
        event = watcher.repeat_event(self.watch, "evt_repeat_5", NOW)
        with patch.object(watcher, "urlopen", return_value=io.BytesIO(b'{"accepted":false,"duplicate":true}')) as opened:
            result = watcher.Brain("http://localhost:8000").post(event)
        self.assertTrue(result["duplicate"])
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:8000/events")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), event)


if __name__ == "__main__":
    unittest.main()
