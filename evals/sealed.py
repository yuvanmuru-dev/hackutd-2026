"""Single-attempt evaluation of the committed, blinded D-053 dataset.

Preflight never calls a scorer. Once receipt.json exists, the attempt is spent,
including on failure. There is deliberately no retry or force option.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

if __package__:
    from . import freeze_model
    from .metrics import benign_summary, summarize
else:
    import freeze_model
    from metrics import benign_summary, summarize

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "agent/packs/guard/data/sealed/manifest.json"
ATTEMPT = Path(__file__).with_name("sealed_run")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_data(manifest_path: Path, runner) -> tuple[dict, dict[str, dict]]:
    """Check hashes, coverage and contracts without importing model inference."""
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("format_version") != 1 or manifest.get("dataset_file") != "scenarios.jsonl":
        raise ValueError("Expected version 1 sealed manifest and scenarios.jsonl")
    path = manifest_path.parent / manifest["dataset_file"]
    if digest(path) != manifest["dataset_sha256"]:
        raise ValueError("Sealed dataset SHA-256 mismatch")
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not cases or len(cases) != manifest["record_count"]:
        raise ValueError("Sealed record count mismatch")
    old = [json.loads(p.read_text()) for p in sorted(
        (ROOT / "agent/packs/guard/data/scenarios").glob("*.json"))]
    old_ids = {s["scenario_id"] for s in old}
    event_ids = {e["event_id"] for s in old for e in s["events"]}
    old_families = {s["generator"]["variant"] for s in old}
    rows, call_owners = {}, {}
    for scenario in cases:
        sid = scenario["scenario_id"]
        if sid in rows or sid in old_ids or runner.errors("DatasetScenario", scenario):
            raise ValueError(f"Duplicate or invalid sealed scenario: {sid}")
        evs = scenario["events"]
        if not evs or sum(e["event_id"] == scenario["trigger_event_id"] for e in evs) != 1:
            raise ValueError(f"Missing/duplicate trigger: {sid}")
        times = [runner.store_module.parse(e["ts"]) for e in evs]
        if times != sorted(times) or sum(e["type"] == "line.region" for e in evs) > 1:
            raise ValueError(f"Invalid chronology or repeated location snapshots: {sid}")
        if scenario["hard_negative"] and scenario["label"] != "legit":
            raise ValueError("Hard negatives must be legit")
        for event in evs:
            if event["user_id"] != scenario["user_id"] or event["source"] != "generator":
                raise ValueError(f"Non-synthetic or cross-user event: {sid}")
            if event["event_id"] in event_ids:
                raise ValueError(f"Reused sealed event ID: {event['event_id']}")
            event_ids.add(event["event_id"])
            cid = event.get("call_id")
            if cid and call_owners.setdefault(cid, sid) != sid:
                raise ValueError("Call ID reused across independent cases")
        rows[sid] = scenario
    families = Counter(s["generator"]["variant"] for s in cases)
    if set(manifest["existing_families"]) != old_families or not old_families <= families.keys():
        raise ValueError("Sealed set must cover every original variant family")
    new = set(manifest["new_families"])
    if len(new) not in (2, 3) or new & old_families or set(families) != old_families | new:
        raise ValueError("Expected two or three genuinely new variant families")
    if dict(Counter(s["label"] for s in cases)) != manifest["labels"]:
        raise ValueError("Sealed label counts mismatch")
    if sum(s["hard_negative"] for s in cases) != manifest["hard_negative_count"]:
        raise ValueError("Sealed hard-negative count mismatch")
    benign = manifest["benign_scenario_ids"]
    if len(benign) < 3 or len(benign) != len(set(benign)) or not set(benign) <= rows.keys():
        raise ValueError("Expected unique sealed benign-text controls")
    for sid in benign:
        s = rows[sid]
        trigger = next(e for e in s["events"] if e["event_id"] == s["trigger_event_id"])
        if s["label"] != "legit" or trigger["type"] != "message.forwarded":
            raise ValueError("Sealed benign controls must be legit forwarded texts")
    return manifest, rows


def claim_attempt(path: Path, provenance: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write(json.dumps({"status": "started", **provenance}, indent=2, sort_keys=True) + "\n")


def markdown(result: dict, percent) -> str:
    meta, brain, rules = result["provenance"], result["brain"], result["rules"]
    headline = "eligible sealed headline run" if meta["headline_eligible"] else "failed model gate; no headline claim"
    lines = ["# Titan sealed evaluation (D-053)", "", f"Status: **{headline}**.",
             f"Mode: **{meta['mode']}**. Single attempt; no post-result tuning or rerun.", "",
             f"Frozen PR #57 merge: `{meta['freeze']['model_commit']}`.",
             f"Final PR head: `{meta['freeze']['model_head_commit']}`.",
             f"Model SHA-256 (canonical file-hash map): `{meta['freeze']['model_sha256']}`.",
             f"Data SHA-256 (raw JSONL): `{meta['dataset_sha256']}`.",
             f"Data source commit: `{meta['data_commit']}`.",
             f"Scored {brain['scored_cases']} synthetic cases. All designed before predictions were inspected.", "",
             "## Rules versus frozen brain", "",
             "Exact class, one versus rest. Precision=TP/(TP+FP), recall=TP/(TP+FN), FPR=FP/(FP+TN). N/A means zero denominator. Recovery scams map under D-051; code relay is coached (D-031).", "",
             "| Threat | Support | Rules precision | Brain precision | Rules recall | Brain recall | Rules FPR | Brain FPR |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for label, row in brain["per_threat"].items():
        base = rules["per_threat"][label]
        lines.append(f"| {label} | {row['support']} | {percent(base['precision'])} | {percent(row['precision'])} | {percent(base['recall'])} | {percent(row['recall'])} | {percent(base['false_positive_rate'])} | {percent(row['false_positive_rate'])} |")
    lines += ["", "| Slice | Support | Rules | Brain |", "|---|---:|---:|---:|",
              f"| Exact-class accuracy | {brain['scored_cases']} | {percent(rules['accuracy'])} | {percent(brain['accuracy'])} |",
              f"| Legit hard-negative any-threat false-alert rate | {brain['hard_negatives']['support']} | {percent(rules['hard_negatives']['false_positive_rate'])} | {percent(brain['hard_negatives']['false_positive_rate'])} |",
              f"| Code-relay coached recall | {brain['code_relay']['support']} | {percent(rules['code_relay']['recall'])} | {percent(brain['code_relay']['recall'])} |", "",
              "## Sealed benign forwarded texts", "",
              "This slice is included in the sealed totals above; it is not the older ten-message development control set.", "",
              "| Scorer | Benign texts | Scam-text false positives | Scam-text FPR | Any-threat false alerts | Any-threat false-alert rate |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for name in ("rules", "brain"):
        row = result["benign_texts"][name]
        lines.append(f"| {name} | {row['support']} | {row['scam_text_false_positives']} | {percent(row['scam_text_false_positive_rate'])} | {row['any_nonlegit_false_alerts']} | {percent(row['any_nonlegit_false_alert_rate'])} |")
    lines += ["", "## Confidence and observed correctness", "",
              "The returned scalar is described, not assumed to be a predicted-class posterior. Rules may return threat risk even when predicting legit. These confidence bands do not establish real-world calibration.", "",
              "| Scorer | Band | Cases | Mean returned probability | Actual exact-class accuracy | Marked calibrated |",
              "|---|---|---:|---:|---:|---:|"]
    for name, summary in (("rules", rules), ("brain", brain)):
        for band, row in summary["calibration"].items():
            lines.append(f"| {name} | {band} | {row['support']} | {percent(row['mean_probability'])} | {percent(row['exact_class_accuracy'])} | {row['calibrated_count']} |")
    lines += ["", "## Provenance and limitations", "",
              f"Brain model labels: `{json.dumps(brain['model_counts'], sort_keys=True)}`.",
              f"Observed ML route status: `{json.dumps(result['model_status'], sort_keys=True)}`.",
              f"Blocked side effects: `{json.dumps(meta['audit'], sort_keys=True)}`.",
              "Fresh Store per case, baseline history before the trigger, incident prefix only, frozen trigger time. Scorers receive neither labels nor variants. No model training or network access occurs.",
              "The original split is test-informed during development and supplies no headline numbers. This sealed sample is synthetic and small; its rates do not establish real-carrier performance.",
              "receipt.json consumes this attempt even on failure. The local exclusive file prevents accidental reruns in this checkout; committed receipts and hashes supply an audit trail, not a tamperproof system.",
              "Full predictions, confusion counts, frozen serving/input hashes, evaluator hashes, Python version and data/design hashes are in results.json and receipt.json. Report weaknesses as found; do not rerun to fix these numbers.", ""]
    return "\n".join(lines)


def execute(args, runner) -> None:
    receipt = ATTEMPT / "receipt.json"
    if receipt.exists():
        raise RuntimeError("Sealed attempt already consumed; preserve receipt/results and report as found")
    snapshot = json.loads(args.freeze.read_text())
    freeze_model.verify_snapshot(snapshot)
    manifest_path = args.sealed_manifest.resolve()
    manifest, rows = load_data(manifest_path, runner)
    data_path = manifest_path.parent / manifest["dataset_file"]
    required = {"manifest.json", "scenarios.jsonl", "DESIGN.md", "generate.py"}
    sources = sorted(p for p in manifest_path.parent.iterdir()
                     if p.is_file() and not p.name.startswith("."))
    if not required <= {p.name for p in sources}:
        raise ValueError("Sealed design, data, manifest and generator must all exist")
    commits = {p.name: runner.committed_source(p) for p in sources}
    if not all(commits.values()):
        raise ValueError("Commit the complete sealed data/design/manifest/generator before scoring")
    if runner.git("diff", "--", "evals") or runner.git("diff", "--cached", "--", "evals"):
        raise ValueError("Commit the evaluator and model freeze before consuming the sealed attempt")
    if runner.git("ls-files", "--others", "--exclude-standard", "--", "evals"):
        raise ValueError("Untracked evaluation files must be committed before the sealed attempt")
    started = datetime.now(timezone.utc).isoformat()
    provenance = {"started_at_utc": started, "dataset_sha256": manifest["dataset_sha256"],
                  "record_count": len(rows), "data_commit": commits[data_path.name],
                  "data_source_commits": commits, "sealed_file_hashes": {p.name: digest(p) for p in sources},
                  "freeze": snapshot, "freeze_file_sha256": digest(args.freeze),
                  "evaluation_commit": runner.git("rev-parse", "HEAD"),
                  "evaluation_hashes": runner.hashes(runner.OUT.glob("*.py")), "python": sys.version}
    # No ML import, model prediction or baseline prediction has occurred yet.
    claim_attempt(receipt, provenance)
    audit = {"network_attempts": 0, "write_attempts": 0, "scenario_read_attempts": 0}
    active, baseline = [], []
    try:
        with runner.offline_read_only(audit, (manifest_path.parent, runner.OUT)):
            active, baseline, model_status = runner.evaluate(
                {"test": list(rows)}, rows, audit, outputs=(active, baseline))
        ready = runner.final_model_ready(model_status, active)
        summary, rules = summarize(active), summarize(baseline)
        names = summary["model_counts"]
        mode = "hybrid model and rules" if any(n.lower().startswith("rules") for n in names) else "model"
        if not any(not n.lower().startswith("rules") for n in names):
            mode = "rules only; frozen model gate failed"
        provenance.update({"completed_at_utc": datetime.now(timezone.utc).isoformat(),
                           "headline_eligible": ready, "mode": mode, "audit": audit})
        ids = set(manifest["benign_scenario_ids"])
        result = {"provenance": provenance, "model_status": model_status,
                  "brain": summary, "rules": rules,
                  "benign_texts": {"brain": benign_summary(r for r in active if r["scenario_id"] in ids),
                                   "rules": benign_summary(r for r in baseline if r["scenario_id"] in ids)},
                  "predictions": active, "rules_predictions": baseline}
        (ATTEMPT / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        text = markdown(result, runner.percent)
        (ATTEMPT / "results.md").write_text(text)
        receipt.write_text(json.dumps({"status": "complete" if ready else "failed_model_gate", **provenance},
                                      indent=2, sort_keys=True) + "\n")
        print(text)
        if not ready:
            raise RuntimeError("Sealed attempt completed without a valid frozen-model route; report as found, no rerun")
    except BaseException as exc:
        # Keep partial predictions even when a caught model failure later aborts.
        (ATTEMPT / "failure.json").write_text(json.dumps({"error": f"{type(exc).__name__}: {exc}",
            "failed_at_utc": datetime.now(timezone.utc).isoformat(), "audit": audit,
            "predictions": active, "rules_predictions": baseline}, indent=2, sort_keys=True) + "\n")
        if not (ATTEMPT / "results.md").exists():
            (ATTEMPT / "results.md").write_text("# Sealed evaluation attempt failed\n\n"
                + f"{type(exc).__name__}: {exc}\n\n"
                + "No headline numbers. Receipt and partial predictions are preserved; do not rerun.\n")
        receipt.write_text(json.dumps({"status": "failed", **provenance,
            "error": f"{type(exc).__name__}: {exc}"}, indent=2, sort_keys=True) + "\n")
        raise
