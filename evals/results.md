# Independent Titan evaluation

Mode: **rules only (model rerun pending)**.

Presentation status: **provisional; final model run pending**.

Rules-only results are provisional. The final post-model run of this script is the source for Devpost/video numbers; do not substitute training scores.

Scorer source on main: `8e6407aa2fdad2795b78ab16912fc74b81845ee6`. Evaluation checkout: `efd15f11010f69bb8a74e2382bc4842a31d4e45e`.
Dataset SHA-256: `d459ebe50ba0c968d86815cc82476294cf67a105b6dfcfaf69e58028feece105`. Split SHA-256: `2fe13d00ccfc3b70d911e2781bad8cc36491ddf4ef01bb25d6be4cbe51d53bd6`.
Scored 137 test cases; train=163, test=137. All 36 hard negatives and the entire code_relay family are held out.

## Per-threat results

Exact class, one versus rest, using the returned threat label without threshold tuning. Precision = TP/(TP+FP); recall = TP/(TP+FN); FPR = FP/(FP+TN). N/A means a zero denominator.

| Threat | Support | Rules precision | Brain precision | Rules recall | Brain recall | Rules FPR | Brain FPR |
|---|---:|---:|---:|---:|---:|---:|---:|
| takeover | 14 | 58.3% | 58.3% | 100.0% | 100.0% | 8.8% | 8.8% |
| coached | 56 | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |
| scam_text | 11 | 100.0% | 100.0% | 90.9% | 90.9% | 0.0% | 0.0% |
| bot | 10 | N/A | N/A | 0.0% | 0.0% | 0.0% | 0.0% |
| legit | 36 | 97.3% | 97.3% | 100.0% | 100.0% | 1.1% | 1.1% |

## Hard negatives and code relay

| Slice | Support | Rules | Brain |
|---|---:|---:|---:|
| Legit hard-negative false-alert rate (any non-legit prediction) | 36 | 0.0% | 0.0% |
| Code-relay coached recall | 44 | 100.0% | 100.0% |

Code relay is part of coached (D-031). The subtype has no distinct predicted label, so no subtype precision is invented. Only eight ordinary legit cases remain in train after all hard-negative variant families are reserved for test.

## Confidence and observed correctness

Returned confidence bands versus exact-class accuracy, on representable labels only. The mean scalar is the scorer's returned probability: the rules use it as threat risk even for a legit prediction, so it is not uniformly a predicted-class posterior. This table is descriptive; no calibrated-probability claim, ECE, or Brier score is inferred from the rules.

| Scorer | Band | Cases | Mean returned probability | Actual exact-class accuracy | Marked calibrated |
|---|---|---:|---:|---:|---:|
| rules | low | 37 | 10.3% | 97.3% | 0 |
| rules | medium | 44 | 55.0% | 100.0% | 0 |
| rules | high | 46 | 91.3% | 78.3% | 0 |
| brain | low | 37 | 10.3% | 97.3% | 0 |
| brain | medium | 44 | 55.0% | 100.0% | 0 |
| brain | high | 46 | 91.3% | 78.3% | 0 |

## Mode and limitations

Brain RiskScore.model counts: `{"rules": 137}`.
ML import/route status: `{"import_error": null, "module_present": false}`. Captured scorer exceptions: `{}`.
Blocked network attempts: 0; blocked file writes: 0; blocked labeled-scenario reads: 0.
The baseline is core.toolbox.rules_score unchanged; the brain column calls core.toolbox.score, which selects the ML implementation automatically when present. Identical rules columns do not demonstrate model improvement.
All 10 recovery_scam test cases were scored, but excluded from exact-class metrics because RiskScore cannot represent that ground-truth class. Their any-threat detection rate is 100.0%; predicted labels: `{"coached": 5, "scam_text": 5}`.
Each case uses a fresh Store, only its user's pre-trigger baseline and incident prefix, and time frozen at the trigger. Later attacker logins are excluded. Whole variants are disjoint, all hard negatives are held out, and the split fingerprint is checked before scoring. No training, tuning, or test-label input to the scorer occurs.
These are small, synthetic, generator-held-out results. They do not establish performance on real carrier data. No benign forwarded-text examples exist in this dataset, so scam-text FPR across other scenario types does not measure benign-text specificity.

## Reproduce

```bash
python3 evals/build_split.py --check
python3 evals/run.py
# After the ML implementation/artifacts are merged into main:
git pull --rebase origin main
python3 evals/run.py --require-model
```

Machine-readable scores, confusion counts, histories/scorer/model hashes, and fallback routing are in results.json.
