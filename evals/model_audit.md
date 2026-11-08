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

A Lane 1 decision is required before final independent claims. The recommended
path is to freeze the model, create a new separate sealed evaluation set, and
evaluate once without further tuning. Alternatively, retain explicit
test-informed/provisional labeling. The original frozen split remains unchanged.
