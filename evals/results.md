# Titan development evaluation

Final headline evidence is the [single sealed evaluation](sealed_run/results.md) (D-058). This file remains development evidence.

Mode: **rules only (model rerun pending)**.

Presentation status: **test-informed during development; provisional, no headline claim**.

D-053/D-053a reserve Devpost/video headline numbers for the single sealed run in sealed_run/results.md. These original-split results remain development evidence even with a model present.

Model training audit: **test_informed**. Model feature/serving rules were selected after reviewing this frozen test set's failure families. Its scores cannot be claimed as untouched independent generalization evidence. See model_audit.md and D-053.

Scorer source on main: `e0c96d42b180e18dfcbf211604465cdc94c91928`. Evaluation checkout: `97e7847046cea6b66824b67d0809dc8445b29590`.
Dataset SHA-256: `d459ebe50ba0c968d86815cc82476294cf67a105b6dfcfaf69e58028feece105`. Split SHA-256: `2fe13d00ccfc3b70d911e2781bad8cc36491ddf4ef01bb25d6be4cbe51d53bd6`.
Scored 137 test cases; train=163, test=137. All 36 hard negatives and the entire code_relay family are held out.

## Per-threat results

Exact class, one versus rest, using the returned threat label without threshold tuning. Precision = TP/(TP+FP); recall = TP/(TP+FN); FPR = FP/(FP+TN). N/A means a zero denominator.

| Threat | Support | Rules precision | Brain precision | Rules recall | Brain recall | Rules FPR | Brain FPR |
|---|---:|---:|---:|---:|---:|---:|---:|
| bot | 10 | N/A | N/A | 0.0% | 0.0% | 0.0% | 0.0% |
| coached | 61 | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |
| legit | 36 | 97.3% | 97.3% | 100.0% | 100.0% | 1.0% | 1.0% |
| scam_text | 16 | 100.0% | 100.0% | 93.8% | 93.8% | 0.0% | 0.0% |
| takeover | 14 | 58.3% | 58.3% | 100.0% | 100.0% | 8.1% | 8.1% |

## Hard negatives and code relay

| Slice | Support | Rules | Brain |
|---|---:|---:|---:|
| Legit hard-negative false-alert rate (any non-legit prediction) | 36 | 0.0% | 0.0% |
| Code-relay coached recall | 44 | 100.0% | 100.0% |

Code relay is part of coached (D-031). The subtype has no distinct predicted label, so no subtype precision is invented. Only eight ordinary legit cases remain in train after all hard-negative variant families are reserved for test.

## Separate benign forwarded-text controls

These evaluation-only controls are outside the frozen development split and are never used for training or tuning. Scam-text FPR = number predicted scam_text / number of benign texts; any other threat prediction is also shown as a false alert.

| Scorer | Benign texts | Scam-text false positives | Scam-text FPR | Any-threat false alerts | Any-threat false-alert rate |
|---|---:|---:|---:|---:|---:|
| rules | 10 | 0 | 0.0% | 0 | 0.0% |
| brain | 10 | 0 | 0.0% | 0 | 0.0% |

Benign controls SHA-256: `b6b21b0fdea0bb645afd6de9a0c2188211ade6caf510c62ff1c61205c7876116`; source commit: `b6953bfb7920eaef5c08e030d9a5456548ff7806`; present on fetched main: `True`.
Ten hand-written synthetic notices are a small control set, not representative benign-text validation.

## Confidence and observed correctness

Returned confidence bands versus exact-class accuracy on the frozen test set (including the D-051 recovery mapping), excluding separate benign controls. The mean scalar is the scorer's returned probability: the rules use it as threat risk even for a legit prediction, so it is not uniformly a predicted-class posterior. This table is descriptive; no calibrated-probability claim, ECE, or Brier score is inferred from the rules.

| Scorer | Band | Cases | Mean returned probability | Actual exact-class accuracy | Marked calibrated |
|---|---|---:|---:|---:|---:|
| rules | high | 51 | 91.2% | 80.4% | 0 |
| rules | low | 37 | 10.3% | 97.3% | 0 |
| rules | medium | 49 | 55.0% | 100.0% | 0 |
| brain | high | 51 | 91.2% | 80.4% | 0 |
| brain | low | 37 | 10.3% | 97.3% | 0 |
| brain | medium | 49 | 55.0% | 100.0% | 0 |

## Mode and limitations

Brain RiskScore.model counts: `{"rules": 137}`.
ML import/route status: `{"import_error": null, "module_present": false}`. Captured scorer exceptions: `{}`.
Blocked network attempts: 0; blocked file writes: 0; blocked labeled-scenario reads: 0.
The baseline is core.toolbox.rules_score unchanged; the brain column calls core.toolbox.score, which selects the ML implementation automatically when present. Identical rules columns do not demonstrate model improvement.
D-051 maps all 10 recovery_scam cases into exact-class metrics: call-based triggers are coached; message.forwarded is scam_text. Original dataset labels and the split are unchanged. Their mapped accuracy is 100.0%; predicted labels: `{"coached": 5, "scam_text": 5}`.
Each case uses a fresh Store, only its user's pre-trigger baseline and incident prefix, and time frozen at the trigger. Later attacker logins are excluded. Whole variants remain disjoint in the frozen split, whose fingerprint is checked before scoring. The model was tuned after inspecting this development set; the scorer receives no labels during this run.
These are small, synthetic, generator-held-out results. They do not establish performance on real carrier data. The primary per-class FPR across all scenario types and the separate benign-text FPR measure different negative populations.

## Development commands

```bash
python3 evals/build_split.py --check
python3 evals/run.py
# Require an installed model, still development evidence:
python3 evals/run.py --require-model
```

Machine-readable scores, confusion counts, histories/scorer/model hashes, and fallback routing are in results.json.
