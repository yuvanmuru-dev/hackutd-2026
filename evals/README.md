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
`agent/packs/guard/data/benign_texts.json` adds ten separate evaluation-only
forwarded-text controls. They never enter the frozen split or training. Their
scam-text false-positive rate has its own table and denominator. Before the data
PR merges, `--benign-texts /path/to/benign_texts.json` can grade that approved
file provisionally with its hash/source commit recorded; a final run requires
the same controls on main.

D-051 maps recovery-scam ground truth to coached for call triggers and scam_text
for `message.forwarded`. All frozen cases remain scored; original data labels
and split bytes stay unchanged. The synthetic dataset and small benign control
set do not establish real-customer detection quality.
