# Lane 2b: ML risk models + evals

**Owner:** Ishan · Codex #2 · **Branch:** `lane/ml` · **Issue:** #35 · **Label:** `lane:ml`
**You own:** `agent/packs/guard/ml/` and `evals/`.
**Read:** docs/PACK_SPEC.md ("Machine learning" and "Detection quality"), the `RiskScore` and `DatasetScenario` types in `contracts/schema.json`.

## Your piece of the story
You turn behavior into **honest numbers**: "coached victim, 87% (calibrated), top reasons ...". The Risk agent and the fast `/check` gate call your `score()`. Your eval numbers (precision, recall, false-positive rate per threat) are the "detection quality" frame in the video, a T-Mobile judging criterion.

## What already exists
- `contracts/fixtures/risk.t1.json`, `risk.t2.json`, `risk.t3.json`: the exact output you return.
- `contracts/fixtures/scenario.t2.json`, `scenario.hard_negative_daughter.json`: the input format. Lane 2a (Yuvan's Codex) commits ~20 seed scenarios first in `agent/packs/guard/data/`, then ~300.
- Brain code that will call you: `agent/core/` (Lane 1). You only provide the function.

## Interface (exact)
```python
# agent/packs/guard/ml/__init__.py
def score(user_id: str, event: dict, history: list[dict]) -> dict:  # returns a RiskScore
    ...
def score_text(text: str) -> dict:  # RiskScore with threat "scam_text" or "legit"
    ...
```
`event` = the trigger `Event`; `history` = that user's recent `Event`s (each with `call_id` when it happened during a call). Must run in < 100 ms and never call the network for `score()` (the `/check` gate uses it).

## Build order
1. **Stub within the first hour:** `score()` returns a rules-based `RiskScore` (`model:"rules"`) using: protection turned off during an unverified call, transfer PIN/code during a call, new device + region mismatch, first-ever action. Check: `python -c "from packs.guard.ml import score; ..."` on the fixtures returns valid JSON matching the schema (`core.contracts.errors("RiskScore", x) == []`). Tell Yuvan.
2. **Features** (`ml/features.py`) from `history` + `event`: during_call, call_unverified, call_minutes, seen_before, protection_off_recent, first_time_action, new_device, region_mismatch, odd_hour_for_user, hesitation_ms, tab_switches, paste_into_pin, otp_during_call. Per-user baselines from that user's legit history.
3. **Personal anomaly:** Isolation Forest per persona on legit scenarios → `anomaly` 0–1.
4. **Risk classifier:** XGBoost multi-class (`takeover/coached/bot/legit`), **isotonic calibration**, SHAP top reasons mapped to plain-English `text` (a dict feature → sentence). Save the model to `ml/models/` (small files OK to commit). `model:"ml+rules"`; hard rules still win as a floor (D-010).
5. **Scam text:** NeMo Retriever embeddings (NVIDIA API, at train time) + logistic regression; `score_text()`. Cache embeddings so tests run offline.
6. **`evals/run.py`:** train on generator variants A, test on held-out variant B; print per-threat precision, recall, **false-positive rate**, a calibration table, and the ablation rules → +anomaly → +classifier. Save `evals/results.md`. Check: one command reproduces the numbers.

## Decisions already made
D-019 sklearn/XGBoost/SHAP, in-process · D-005 synthetic data only · D-015 NVIDIA only for embeddings · D-021 Brev GPU training optional (#39).

## Stop and ask Lane 1 if...
- you need a feature the data doesn't have (ask Lane 2a for the field, don't invent data).
- `RiskScore` needs a new field.
- you want deep learning / a hosted ML service.

## Pitfalls
- Leakage: don't train and test on the same generator variant or the numbers are meaningless; judges will ask "would this work on real data?"
- Report the false-positive rate honestly, especially on hard negatives (Maya's long call with her daughter must stay legit).
- `confidence` words: high ≥ 0.8, medium 0.5–0.8, low < 0.5 (agree with Lane 1 if you change this).

## Definition of done
`score()` and `score_text()` return valid `RiskScore`s fast; `evals/run.py` prints the numbers; PR `[lane 2b] ...` with `Closes #35`.

## Teammate guide (Ishan)
- **Good first answer:** ships the rules stub first, then features, then models; mentions held-out variants and false-positive rate.
- **Check-in:** "What's the false-positive rate on hard negatives?" · "Show me the top reasons for the T2 fixture."
- **Red flags:** trains a neural net; tests on training data; returns a different shape; reads data from anywhere but `agent/packs/guard/data/`.
