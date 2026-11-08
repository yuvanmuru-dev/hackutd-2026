# Model training provenance audit

Audited PR #57 at `044762137bd861c0708778d108ac9bcbb3b2e828` without scoring it or changing ML files.

The frozen split was used for feature/rule selection. The current test scores
would be test-informed and optimistic, rather than an untouched independent
estimate. This does not change the split's train/test membership.

Evidence in that head:

- `agent/packs/guard/ml/models/meta.json:69-74` explicitly records choosing call
  gating, store-channel features and a serving threshold after held-out failure
  review.
- `agent/packs/guard/ml/text.py:15-16` records adding the no-link credential rule
  after reviewing `code_request_no_link`.
- `seed_scam_text_04.json` is that variant and is in the frozen test list only.

The recorded split hash matches our frozen bytes. Weight fitting otherwise uses
125 risk scenarios from the train list plus 49 allowed normal-history examples;
calibration uses training out-of-fold predictions. No hard negatives or test
variants appear in those fit inputs.

Inference is pure Python and offline. Risk results are `ml+rules`; text results
are intentionally `rules`. The evaluator distinguishes a valid rules score
returned by the ML entry point from an empty/error-driven brain fallback.

D-053/D-053a resolve this audit: the original split is **test-informed during
development**. Lane 2b may tune against it until T+12, then the final PR #57
head/merge commit are frozen. A new independently designed sealed set is scored
once after that freeze and supplies the only headline Devpost/video numbers.
The original frozen split remains unchanged.

## Completed sealed evaluation (D-058)

Frozen model: `67fe7df582a63f4f871eea27867391d55e6a8d16` (PR #57),
head `3d66c258692031bd740757df42d011549d9c4984`. All 11 ML files on fetched
main matched that merge; the canonical file-hash aggregate is
`fe2a9b18314624ae3507d029f53110b0d539c87f54005287e9d9392d3a8140d2`.

The sealed set was scored **once**, completed 2026-11-08T07:03:19Z, in an
isolated checkout of the exact frozen runtime with committed evaluator code.
A later unrelated Brev change in core/llm.py on main was excluded by using the
frozen checkout. The independently authored data remained unchanged:
SHA-256 `c20095a240dc38423d3a3c9e90ac36c597215128d6b39ed4fb5f9e143d86b910`.

The hybrid scored 105/138 exact classes correctly (76.1%), versus 115/138
(83.3%) for core.toolbox.rules_score. Scam-text recall was 6/30 (20.0%)
versus 28/30 (93.3%); hard-negative false alerts were 9/33 (27.3%) versus
0/33. Both scorers had 0/6 benign-text false positives. These weaknesses are
preserved as found, with no rerun or post-result tuning. The saved predictions
were independently checked by arithmetic only.

See [sealed results](sealed_run/results.md) and [receipt](sealed_run/receipt.json)
for full rates, model routes, confidence table and hashes. This is small
synthetic evaluation evidence, not a real-carrier performance estimate.
