# Independent evaluation (D-049)

`split.json` is frozen before scoring. Its `train` and `test` arrays contain
repository-relative scenario JSON paths. The ML lane must train/tune only with
`train`; `test` is reserved for this independent evaluator. Whole
`generator.variant` groups stay together, and all hard-negative groups are in
test. The entire `code_relay` group is held out. This leaves eight ordinary legit
cases in train; normal persona histories can supply baseline features.

```bash
python3 evals/build_split.py --check
python3 -m unittest evals.test_metrics evals.test_run -v
python3 evals/run.py
```

The runner checks the frozen dataset fingerprint and that agent source matches
fetched `origin/main`. It replays each scenario independently, loads only that
person's baseline events before the trigger, and freezes time at that trigger.
Future events, labels and variants are never passed to the scorer. Scoring is
offline and cannot train or write files. Any attempted side effect fails the run,
even if `core.toolbox.score` catches the underlying exception.

`results.md` is the readable report; `results.json` contains every test prediction,
confusion counts, scorer/model/data hashes and observed model fallbacks. Rules
and the brain scorer are evaluated on identical reconstructed inputs. Rules-only
results remain provisional. After Ishan's model reaches main:

```bash
git pull --rebase origin main
python3 evals/run.py --require-model
```

Only that post-model independent run should supply Devpost/video numbers.
The dataset is synthetic, lacks benign forwarded-text examples, and has a small
test set; the report states those limits. Recovery-scam cases are scored and
reported separately because the current RiskScore contract cannot name that
ground-truth label.
