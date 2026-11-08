# Titan evaluation (D-049, D-053/D-058)

Only the **single sealed run** supplies headline Devpost/video numbers.
`results.md` / `results.json` describe the original split and remain
**test-informed during development**, including after a model lands.

## What we ship

The sealed test ran **once**, with frozen model `67fe7df` and data SHA-256 `c20095a240dc38423d3a3c9e90ac36c597215128d6b39ed4fb5f9e143d86b910`.

- Calls and account events use hybrid `ml+rules`: **30/30 coached cases**, versus rules-only **21/30**. It was the only tested scorer that caught bots: **12/12**, versus rules-only **0/12**.
- Forwarded texts (`message.forwarded`) use `rules_score`: **28/30 scam texts**, versus hybrid **6/30**, with **0/6 benign false positives for both scorers**.

Routing was chosen **after seeing the sealed results** ([D-060](../docs/DECISIONS.md)). These are measured component results; **no combined sealed score is claimed**, and the routed system was not scored on the sealed set. Dev-split numbers remain **test-informed during development**. All data are synthetic, so no real-carrier performance claim is made. Full component results and limitations remain in the [sealed report](sealed_run/results.md).

The canonical sealed attempt completed once at **2026-11-08 01:03 Chicago**.
Model commit: `67fe7df582a63f4f871eea27867391d55e6a8d16`.
See [the sealed report](sealed_run/results.md), [receipt](sealed_run/receipt.json)
and [main/frozen ML hash verification](main_model_verification.json).
The attempt is consumed: **do not rerun**. Frozen runtime and evaluator source
commits remain in git history; later integration changes do not redefine them.

## Historical design protocol

Lane 2b may tune against the original development split until T+12
(00:30 Chicago, 8 November 2026; `2026-11-08T06:30:00Z`). The data lane builds
sealed data independently and keeps it local and unpublished until that
deadline and the final PR #57 head are frozen. Lane 2b must not read it.
No scorer is run on those examples during design or validation.

The sealed author fixes `DESIGN.md` before generating cases: fresh seeds for
all existing families plus three new families, hard negatives and benign
forwarded texts. `manifest.json` records counts, family coverage and the raw
SHA-256 of `scenarios.jsonl`. All four data/design files are committed before
scoring. The original split is never rewritten.

```bash
python3 evals/build_split.py --check
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest evals.test_metrics evals.test_run evals.test_freeze_model evals.test_sealed -v
```

Tests use invented temporary fixtures for sealed execution. They do not score
the actual sealed set or consume its receipt.

## Historical freeze and single-attempt procedure

At the deadline, record #57's final head with GitHub; after its merge verify
that exact head is the merge's second parent and fetch main. The helper also
rejects model-head commits dated after the tuning cutoff. Use the exact
merged scorer checkout: serving code, artifacts,
baseline history, personas, contracts and Store fixtures must match that
commit. Later unrelated main changes do not redefine the frozen scorer.

```bash
git fetch origin main
python3 evals/freeze_model.py --commit FULL_PR57_MERGE_SHA --model-head FULL_FINAL_PR57_HEAD_SHA
git add evals/frozen_model.json
git commit -m "[lane 2c] record frozen model provenance"
# Only after sealed data/design and evaluator sources are committed:
python3 evals/run.py --sealed
```

`--sealed-manifest /absolute/path/to/manifest.json` can use the committed data
lane worktree without copying data across lane boundaries. `--freeze` can name
an explicitly recorded freeze file. Defaults are the repo's sealed manifest
and `evals/frozen_model.json`.

Preflight validates data SHA, contracts, coverage, source commits and the
frozen serving/input bytes without model inference. It then exclusively
creates `evals/sealed_run/receipt.json` **before importing the ML module or
scoring any case**. That consumes the attempt on success, interruption or
failure. There is no retry/force switch. Preserve and commit the receipt,
results and any failure file; do not delete them or rerun from a fresh
checkout. The exclusive local file prevents accidental retries in that
checkout; committed artifacts provide the cross-checkout audit trail.

`sealed_run/results.md` prints exact-class precision/recall/FPR, hard-negative
false alerts, code-relay recall, a separate sealed benign-text FPR table,
confidence bands and rules versus brain. `results.json` contains predictions,
confusion counts, model routing and provenance. Headline eligibility requires
the frozen ML implementation on every brain route without errors; deliberate
text-rules routes remain labeled **hybrid model and rules**. Failure or empty
model fallback is reported as found, with no attempt to fix and rerun.

Each case uses a fresh Store, only its user's pre-trigger baseline and incident
prefix, and frozen trigger time. Later attacker logins, labels and variants
never reach the scorer. Network access, writes and reads of labeled datasets,
design and generator files during scoring are blocked and counted, even if
the brain catches the error.

## Development evidence

`split.json` has 163 train / 137 test repository-relative paths. Whole
`generator.variant` groups stay together, all 36 hard negatives and the entire
`code_relay` group remain in test. `build_split.py --check` checks its original
fingerprint. `model_audit.md` explains why this originally held-out split
became development evidence under D-053.

```bash
python3 evals/run.py
python3 evals/run.py --require-model  # requires model routing; still development evidence
```

The ten evaluation-only controls in
`agent/packs/guard/data/benign_texts.json` are outside the split and training;
their own table has a separate denominator. `--benign-texts /path/to/file`
supports a provisional committed control file before its data PR merges.
They are not substituted for the new benign controls in the sealed run.

D-031 labels code relay coached. D-051 maps recovery scams to coached for call
triggers and scam_text for forwarded messages. Rates on small synthetic data
do not establish real-carrier performance; returned confidence scalars are
descriptive and not assumed to be predicted-class posteriors.
