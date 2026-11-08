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


def evaluation_label(label: str, trigger_type: str | None = None) -> str:
    """Map dataset recovery scams to representable classes under D-051."""
    if label == "recovery_scam":
        if not isinstance(trigger_type, str) or not trigger_type.strip():
            raise ValueError("recovery_scam requires trigger_type for D-051 mapping")
        return "scam_text" if trigger_type == "message.forwarded" else "coached"
    if label not in THREATS:
        raise ValueError(f"unsupported ground-truth label: {label}")
    return label


def benign_summary(records: Iterable[dict]) -> dict:
    """Describe false alerts on separate all-legit message controls."""
    rows = list(records)
    if any(row["label"] != "legit" for row in rows):
        raise ValueError("benign controls must all have ground-truth label legit")
    scam_text = sum(row["prediction"]["threat"] == "scam_text" for row in rows)
    false_alerts = sum(row["prediction"]["threat"] != "legit" for row in rows)
    return {
        "support": len(rows),
        "scam_text_false_positives": scam_text,
        "scam_text_false_positive_rate": _rate(scam_text, len(rows)),
        "any_nonlegit_false_alerts": false_alerts,
        "any_nonlegit_false_alert_rate": _rate(false_alerts, len(rows)),
    }


def summarize(records: Iterable[dict]) -> dict:
    """Summarize rows with label, trigger_type, hard_negative and prediction.

prediction is the returned RiskScore. D-051 maps recovery_scam to coached for
call triggers and scam_text for forwarded messages, so every case participates
in exact-class metrics. The original rows and labels remain unchanged. Recovery
also receives a separate any-nonlegit detection result. Code relay is a coached
subgroup, not a predicted class. Hard-negative FPR means any nonlegit alert.
"""
    rows = [{**row, "_evaluation_label": evaluation_label(row["label"], row.get("trigger_type"))}
            for row in records]
    for row in rows:
        if row["hard_negative"] and row["label"] != "legit":
            raise ValueError("hard negatives must have ground-truth label legit")
        score = row["prediction"]
        if score["confidence"] not in CONFIDENCE_BANDS:
            raise ValueError(f"unsupported confidence band: {score['confidence']}")
        probability = score["probability"]
        if isinstance(probability, bool) or not isinstance(probability, (float, int)) \
                or not isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("probability must be a finite number in [0, 1]")

    per_threat = {}
    for threat in THREATS:
        tp = sum(row["_evaluation_label"] == threat and row["prediction"]["threat"] == threat for row in rows)
        fp = sum(row["_evaluation_label"] != threat and row["prediction"]["threat"] == threat for row in rows)
        fn = sum(row["_evaluation_label"] == threat and row["prediction"]["threat"] != threat for row in rows)
        tn = len(rows) - tp - fp - fn
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
    code_relay = [row for row in rows if row["label"] == "coached" and row["variant"] == "code_relay"]
    relay_detected = sum(row["prediction"]["threat"] == "coached" for row in code_relay)
    recovery = [row for row in rows if row["label"] == "recovery_scam"]
    recovery_detected = sum(row["prediction"]["threat"] != "legit" for row in recovery)
    recovery_correct = sum(row["prediction"]["threat"] == row["_evaluation_label"] for row in recovery)

    calibration = {}
    for band in CONFIDENCE_BANDS:
        members = [row for row in rows if row["prediction"]["confidence"] == band]
        count = len(members)
        correct = sum(row["prediction"]["threat"] == row["_evaluation_label"] for row in members)
        calibrated = sum(row["prediction"]["calibrated"] is True for row in members)
        calibration[band] = {
            "support": count,
            "mean_probability": _rate(sum(row["prediction"]["probability"] for row in members), count),
            "exact_class_correct": correct,
            "exact_class_accuracy": _rate(correct, count),
            "calibrated_count": calibrated,
            "calibrated_fraction": _rate(calibrated, count),
        }

    correct = sum(row["prediction"]["threat"] == row["_evaluation_label"] for row in rows)
    return {
        "scored_cases": len(rows),
        "exact_class_cases": len(rows),
        "excluded_cases": {},
        "accuracy": _rate(correct, len(rows)),
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
            "mapped_exact_class_correct": recovery_correct,
            "mapped_exact_class_accuracy": _rate(recovery_correct, len(recovery)),
            "predicted_labels": dict(sorted(Counter(row["prediction"]["threat"] for row in recovery).items())),
        },
        "calibration": calibration,
        "model_counts": dict(sorted(Counter(row["prediction"]["model"] for row in rows).items())),
    }
