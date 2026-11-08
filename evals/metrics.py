"""Independent descriptive metrics for the frozen synthetic test set.

Rates are fractions in [0, 1]. A rate with no denominator is None, so callers
can display N/A instead of manufacturing a zero. The returned probability is
reported descriptively; it is not assumed to be predicted-class confidence.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from typing import Iterable


THREATS = ("takeover", "coached", "scam_text", "bot", "legit")
CONFIDENCE_BANDS = ("low", "medium", "high")


def _rate(numerator: int | float, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize(records: Iterable[dict]) -> dict:
    """Summarize rows with label, hard_negative, variant and prediction fields.

prediction is the returned RiskScore. All rows are counted as scored, but true
recovery_scam rows are excluded from exact-class metrics because that label is
not representable by the current RiskScore contract. They receive a separate
any-nonlegit detection result. Code relay is a coached subgroup, not a seventh
predicted class. Hard-negative false-positive rate means any nonlegit alert.
"""
    rows = list(records)
    for row in rows:
        if row["label"] not in (*THREATS, "recovery_scam"):
            raise ValueError(f"unsupported ground-truth label: {row['label']}")
        if row["hard_negative"] and row["label"] != "legit":
            raise ValueError("hard negatives must have ground-truth label legit")
        score = row["prediction"]
        if score["confidence"] not in CONFIDENCE_BANDS:
            raise ValueError(f"unsupported confidence band: {score['confidence']}")
        probability = score["probability"]
        if isinstance(probability, bool) or not isinstance(probability, (float, int)) \
                or not isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("probability must be a finite number in [0, 1]")

    supported = [row for row in rows if row["label"] in THREATS]
    excluded = Counter(row["label"] for row in rows if row["label"] not in THREATS)
    per_threat = {}
    for threat in THREATS:
        tp = sum(row["label"] == threat and row["prediction"]["threat"] == threat for row in supported)
        fp = sum(row["label"] != threat and row["prediction"]["threat"] == threat for row in supported)
        fn = sum(row["label"] == threat and row["prediction"]["threat"] != threat for row in supported)
        tn = len(supported) - tp - fp - fn
        per_threat[threat] = {
            "support": tp + fn,
            "predicted": tp + fp,
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": _rate(tp, tp + fp),
            "recall": _rate(tp, tp + fn),
            "false_positive_rate": _rate(fp, fp + tn),
        }

    hard_negatives = [row for row in rows if row["hard_negative"]]
    false_alerts = sum(row["prediction"]["threat"] != "legit" for row in hard_negatives)
    code_relay = [row for row in supported if row["label"] == "coached" and row["variant"] == "code_relay"]
    relay_detected = sum(row["prediction"]["threat"] == "coached" for row in code_relay)
    recovery = [row for row in rows if row["label"] == "recovery_scam"]
    recovery_detected = sum(row["prediction"]["threat"] != "legit" for row in recovery)

    calibration = {}
    for band in CONFIDENCE_BANDS:
        members = [row for row in supported if row["prediction"]["confidence"] == band]
        count = len(members)
        correct = sum(row["prediction"]["threat"] == row["label"] for row in members)
        calibrated = sum(row["prediction"]["calibrated"] is True for row in members)
        calibration[band] = {
            "support": count,
            "mean_probability": _rate(sum(row["prediction"]["probability"] for row in members), count),
            "exact_class_correct": correct,
            "exact_class_accuracy": _rate(correct, count),
            "calibrated_count": calibrated,
            "calibrated_fraction": _rate(calibrated, count),
        }

    correct = sum(row["prediction"]["threat"] == row["label"] for row in supported)
    return {
        "scored_cases": len(rows),
        "exact_class_cases": len(supported),
        "excluded_cases": dict(sorted(excluded.items())),
        "accuracy": _rate(correct, len(supported)),
        "per_threat": per_threat,
        "hard_negatives": {
            "support": len(hard_negatives),
            "false_alerts": false_alerts,
            "correct_legit": len(hard_negatives) - false_alerts,
            "false_positive_rate": _rate(false_alerts, len(hard_negatives)),
        },
        "code_relay": {"support": len(code_relay), "coached_detected": relay_detected,
                       "recall": _rate(relay_detected, len(code_relay))},
        "recovery_scam": {
            "support": len(recovery), "nonlegit_detected": recovery_detected,
            "detection_rate": _rate(recovery_detected, len(recovery)),
            "predicted_labels": dict(sorted(Counter(row["prediction"]["threat"] for row in recovery).items())),
        },
        "calibration": calibration,
        "model_counts": dict(sorted(Counter(row["prediction"]["model"] for row in rows).items())),
    }
