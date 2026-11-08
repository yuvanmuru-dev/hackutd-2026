# Titan sealed evaluation (D-053)

Status: **eligible sealed headline run**.
Mode: **hybrid model and rules**. Single attempt; no post-result tuning or rerun.

Frozen PR #57 merge: `67fe7df582a63f4f871eea27867391d55e6a8d16`.
Final PR head: `3d66c258692031bd740757df42d011549d9c4984`.
Model SHA-256 (canonical file-hash map): `fe2a9b18314624ae3507d029f53110b0d539c87f54005287e9d9392d3a8140d2`.
Data SHA-256 (raw JSONL): `c20095a240dc38423d3a3c9e90ac36c597215128d6b39ed4fb5f9e143d86b910`.
Data source commit: `3c513b4ca194593992ed80fb844b791012e37226`.
Scored 138 synthetic cases. All designed before predictions were inspected.

## Rules versus frozen brain

Exact class, one versus rest. Precision=TP/(TP+FP), recall=TP/(TP+FN), FPR=FP/(FP+TN). N/A means zero denominator. Recovery scams map under D-051; code relay is coached (D-031).

| Threat | Support | Rules precision | Brain precision | Rules recall | Brain recall | Rules FPR | Brain FPR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| takeover | 24 | 66.7% | 72.7% | 100.0% | 100.0% | 10.5% | 7.9% |
| coached | 30 | 100.0% | 100.0% | 70.0% | 100.0% | 0.0% | 0.0% |
| scam_text | 30 | 100.0% | 100.0% | 93.3% | 20.0% | 0.0% | 0.0% |
| bot | 12 | N/A | 100.0% | 0.0% | 100.0% | 0.0% | 0.0% |
| legit | 42 | 79.2% | 57.9% | 100.0% | 78.6% | 11.5% | 25.0% |

| Slice | Support | Rules | Brain |
|---|---:|---:|---:|
| Exact-class accuracy | 138 | 83.3% | 76.1% |
| Legit hard-negative any-threat false-alert rate | 33 | 0.0% | 27.3% |
| Code-relay coached recall | 3 | 100.0% | 100.0% |

## Sealed benign forwarded texts

This slice is included in the sealed totals above; it is not the older ten-message development control set.

| Scorer | Benign texts | Scam-text false positives | Scam-text FPR | Any-threat false alerts | Any-threat false-alert rate |
|---|---:|---:|---:|---:|---:|---:|
| rules | 6 | 0 | 0.0% | 0 | 0.0% |
| brain | 6 | 0 | 0.0% | 0 | 0.0% |

## Confidence and observed correctness

The returned scalar is described, not assumed to be a predicted-class posterior. Rules may return threat risk even when predicting legit. These confidence bands do not establish real-world calibration.

| Scorer | Band | Cases | Mean returned probability | Actual exact-class accuracy | Marked calibrated |
|---|---|---:|---:|---:|---:|
| rules | low | 53 | 11.5% | 79.2% | 0 |
| rules | medium | 26 | 58.8% | 100.0% | 0 |
| rules | high | 59 | 89.7% | 79.7% | 0 |
| brain | low | 30 | 11.7% | 20.0% | 0 |
| brain | medium | 15 | 60.6% | 40.0% | 0 |
| brain | high | 93 | 98.1% | 100.0% | 87 |

## Provenance and limitations

Brain model labels: `{"ml+rules": 102, "rules": 36}`.
Observed ML route status: `{"import_error": null, "module_present": true}`.
Blocked side effects: `{"network_attempts": 0, "scenario_read_attempts": 0, "write_attempts": 0}`.
Fresh Store per case, baseline history before the trigger, incident prefix only, frozen trigger time. Scorers receive neither labels nor variants. No model training or network access occurs.
The original split is test-informed during development and supplies no headline numbers. This sealed sample is synthetic and small; its rates do not establish real-carrier performance.
receipt.json consumes this attempt even on failure. The local exclusive file prevents accidental reruns in this checkout; committed receipts and hashes supply an audit trail, not a tamperproof system.
Full predictions, confusion counts, frozen serving/input hashes, evaluator hashes, Python version and data/design hashes are in results.json and receipt.json. Report weaknesses as found; do not rerun to fix these numbers.
