"""Hand-calculated metric checks, independent of model implementation."""
import unittest

from evals.metrics import summarize


def row(label, prediction, *, variant="example", hard_negative=False,
        confidence="high", probability=0.9, calibrated=False):
    return {"scenario_id": "scn_test", "label": label, "variant": variant,
            "hard_negative": hard_negative,
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

    def test_recovery_is_scored_but_excluded_from_exact_class_metrics(self):
        result = summarize([
            row("takeover", "takeover"),
            row("recovery_scam", "coached"),
            row("recovery_scam", "legit"),
        ])
        self.assertEqual(result["scored_cases"], 3)
        self.assertEqual(result["exact_class_cases"], 1)
        self.assertEqual(result["excluded_cases"], {"recovery_scam": 2})
        self.assertEqual(result["per_threat"]["coached"]["fp"], 0)
        self.assertEqual(result["calibration"]["high"]["support"], 1)
        self.assertEqual(result["recovery_scam"]["nonlegit_detected"], 1)
        self.assertEqual(result["recovery_scam"]["detection_rate"], 0.5)
        self.assertEqual(result["recovery_scam"]["predicted_labels"], {"coached": 1, "legit": 1})
        self.assertEqual(result["model_counts"], {"test": 3})

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
