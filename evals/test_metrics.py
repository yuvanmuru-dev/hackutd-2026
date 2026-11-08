"""Hand-calculated metric checks, independent of model implementation."""
import copy
import unittest

from evals.metrics import benign_summary, evaluation_label, summarize


def row(label, prediction, *, variant="example", hard_negative=False,
        confidence="high", probability=0.9, calibrated=False, trigger_type=None):
    return {"scenario_id": "scn_test", "label": label, "variant": variant,
            "hard_negative": hard_negative, "trigger_type": trigger_type,
            "prediction": {"threat": prediction, "probability": probability,
                           "confidence": confidence, "calibrated": calibrated, "model": "test"}}


class MetricsTests(unittest.TestCase):
    def test_one_vs_rest_counts_and_rates(self):
        result = summarize([
            row("takeover", "takeover"), row("takeover", "legit"),
            row("legit", "takeover"), row("legit", "legit"),
            row("coached", "coached"), row("scam_text", "scam_text"),
        ])
        actual = result["per_threat"]["takeover"]
        self.assertEqual({key: actual[key] for key in ("tp", "fp", "tn", "fn")},
                         {"tp": 1, "fp": 1, "tn": 3, "fn": 1})
        self.assertEqual(actual["support"], 2)
        self.assertEqual(actual["precision"], 0.5)
        self.assertEqual(actual["recall"], 0.5)
        self.assertEqual(actual["false_positive_rate"], 0.25)
        self.assertAlmostEqual(result["accuracy"], 4 / 6)

    def test_zero_denominators_are_undefined(self):
        empty = summarize([])
        self.assertIsNone(empty["accuracy"])
        self.assertIsNone(empty["hard_negatives"]["false_positive_rate"])
        self.assertIsNone(empty["calibration"]["high"]["mean_probability"])
        result = summarize([row("takeover", "legit")])["per_threat"]
        self.assertIsNone(result["takeover"]["precision"])
        self.assertEqual(result["takeover"]["recall"], 0.0)
        self.assertIsNone(result["takeover"]["false_positive_rate"])
        self.assertIsNone(result["coached"]["recall"])

    def test_hard_negative_rate_counts_any_threat_alert(self):
        result = summarize([
            row("legit", "legit", hard_negative=True),
            row("legit", "takeover", hard_negative=True),
            row("legit", "coached", hard_negative=True),
            row("legit", "scam_text"),
        ])["hard_negatives"]
        self.assertEqual(result["support"], 3)
        self.assertEqual(result["false_alerts"], 2)
        self.assertEqual(result["correct_legit"], 1)
        self.assertAlmostEqual(result["false_positive_rate"], 2 / 3)

    def test_recovery_is_mapped_into_exact_class_metrics_without_mutation(self):
        rows = [
            row("takeover", "takeover"),
            row("recovery_scam", "coached", trigger_type="otp.sent"),
            row("recovery_scam", "scam_text", trigger_type="message.forwarded"),
            row("recovery_scam", "legit", trigger_type="transfer_pin.requested"),
        ]
        before = copy.deepcopy(rows)
        result = summarize(rows)
        self.assertEqual(rows, before)
        self.assertEqual(result["scored_cases"], 4)
        self.assertEqual(result["exact_class_cases"], 4)
        self.assertEqual(result["excluded_cases"], {})
        self.assertEqual(result["per_threat"]["coached"]["tp"], 1)
        self.assertEqual(result["per_threat"]["coached"]["fn"], 1)
        self.assertEqual(result["per_threat"]["coached"]["fp"], 0)
        self.assertEqual(result["per_threat"]["scam_text"]["tp"], 1)
        self.assertEqual(result["calibration"]["high"]["support"], 4)
        self.assertEqual(result["calibration"]["high"]["exact_class_accuracy"], 0.75)
        self.assertEqual(result["recovery_scam"]["nonlegit_detected"], 2)
        self.assertAlmostEqual(result["recovery_scam"]["detection_rate"], 2 / 3)
        self.assertEqual(result["recovery_scam"]["mapped_exact_class_correct"], 2)
        self.assertAlmostEqual(result["recovery_scam"]["mapped_exact_class_accuracy"], 2 / 3)
        self.assertEqual(result["recovery_scam"]["predicted_labels"], {"coached": 1, "legit": 1, "scam_text": 1})
        self.assertEqual(result["model_counts"], {"test": 4})

    def test_evaluation_label_requires_recovery_trigger(self):
        self.assertEqual(evaluation_label("recovery_scam", "message.forwarded"), "scam_text")
        self.assertEqual(evaluation_label("recovery_scam", "otp.sent"), "coached")
        self.assertEqual(evaluation_label("legit", None), "legit")
        for missing in (None, "", "  "):
            with self.subTest(trigger=missing), self.assertRaises(ValueError):
                evaluation_label("recovery_scam", missing)
        with self.assertRaises(ValueError):
            summarize([row("recovery_scam", "coached")])

    def test_benign_controls_report_scam_text_and_any_threat_separately(self):
        rows = [row("legit", "legit"), row("legit", "scam_text"), row("legit", "coached")]
        before = copy.deepcopy(rows)
        result = benign_summary(rows)
        self.assertEqual(rows, before)
        self.assertEqual(result["support"], 3)
        self.assertEqual(result["scam_text_false_positives"], 1)
        self.assertAlmostEqual(result["scam_text_false_positive_rate"], 1 / 3)
        self.assertEqual(result["any_nonlegit_false_alerts"], 2)
        self.assertAlmostEqual(result["any_nonlegit_false_alert_rate"], 2 / 3)
        self.assertIsNone(benign_summary([])["scam_text_false_positive_rate"])
        self.assertIsNone(benign_summary([])["any_nonlegit_false_alert_rate"])
        with self.assertRaises(ValueError):
            benign_summary([row("coached", "legit")])

    def test_relay_is_a_coached_subgroup_and_calibration_is_descriptive(self):
        result = summarize([
            row("coached", "coached", variant="code_relay", probability=0.8, calibrated=True),
            row("coached", "legit", variant="code_relay", probability=0.1, confidence="low"),
            row("coached", "coached", variant="port_out", probability=0.6, confidence="medium"),
            row("legit", "legit", probability=0.1, confidence="low"),
        ])
        self.assertEqual(result["code_relay"], {"support": 2, "coached_detected": 1, "recall": 0.5})
        self.assertAlmostEqual(result["per_threat"]["coached"]["recall"], 2 / 3)
        low = result["calibration"]["low"]
        self.assertEqual(low["support"], 2)
        self.assertEqual(low["exact_class_correct"], 1)
        self.assertEqual(low["exact_class_accuracy"], 0.5)
        self.assertEqual(low["mean_probability"], 0.1)
        self.assertEqual(result["calibration"]["high"]["calibrated_count"], 1)

    def test_invalid_inputs_do_not_silently_produce_rates(self):
        with self.assertRaises(ValueError):
            summarize([row("coached", "coached", hard_negative=True)])
        for invalid in (True, float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(probability=invalid), self.assertRaises(ValueError):
                summarize([row("legit", "legit", probability=invalid)])


if __name__ == "__main__":
    unittest.main()
