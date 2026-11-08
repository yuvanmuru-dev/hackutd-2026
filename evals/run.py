"""Offline Titan evaluation: development split, or one sealed attempt (D-053).

Run from the repository root: python3 evals/run.py
Use --sealed for headline evidence. The original split is development-only.
"""
from __future__ import annotations

import argparse
import builtins
from collections import Counter
from contextlib import contextmanager, ExitStack
import copy
from datetime import datetime, timezone
import datetime as datetime_module
import hashlib
import importlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

if __package__:
    from .build_split import ROOT, SPLIT, validate
    from .metrics import benign_summary, summarize
else:
    from build_split import ROOT, SPLIT, validate
    from metrics import benign_summary, summarize

sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "agent"))
from core import events, store as store_module, toolbox
from core.contracts import errors

OUT = Path(__file__).resolve().parent
BENIGN_TEXTS = ROOT / "agent/packs/guard/data/benign_texts.json"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def committed_source(path: Path) -> str | None:
    """Attribute control bytes to a commit only when that commit contains them."""
    try:
        repo = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                    cwd=path.parent, text=True, stderr=subprocess.DEVNULL).strip()).resolve()
        relative = path.resolve().relative_to(repo).as_posix()
        commit = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", relative],
                    cwd=repo, text=True, stderr=subprocess.DEVNULL).strip()
        content = subprocess.check_output(["git", "show", f"{commit}:{relative}"],
                    cwd=repo, stderr=subprocess.DEVNULL)
        return commit if hashlib.sha256(content).hexdigest() == file_hash(path) else None
    except (subprocess.CalledProcessError, OSError, ValueError):
        return None


def hashes(paths) -> dict[str, str]:
    return {p.relative_to(ROOT).as_posix(): file_hash(p) for p in sorted(paths)
            if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith(".")}


@contextmanager
def offline_read_only(audit: dict, extra_forbidden=()):
    """Never let an implicitly caught provider error masquerade as model success."""
    original_open, original_io_open = builtins.open, io.open
    forbidden_paths = {Path(p).resolve() for p in extra_forbidden} | {BENIGN_TEXTS.resolve()}
    forbidden_dirs = {p for p in forbidden_paths if p.is_dir()} | {
        ROOT / "agent/packs/guard/data/sealed"}

    def deny_network(*_args, **_kwargs):
        audit["network_attempts"] += 1
        raise RuntimeError("Evaluation scoring must run offline")

    def guarded_open(original):
        def open_file(file, mode="r", *args, **kwargs):
            if isinstance(file, (str, bytes, Path)):
                path = Path(file).resolve() if not isinstance(file, bytes) else Path(file.decode()).resolve()
                scenario_dir = ROOT / "agent/packs/guard/data/scenarios"
                if path.is_relative_to(scenario_dir) or path in forbidden_paths \
                        or any(path.is_relative_to(folder) for folder in forbidden_dirs):
                    audit["scenario_read_attempts"] = audit.get("scenario_read_attempts", 0) + 1
                    raise RuntimeError("Scorer must not read labeled scenario files during evaluation")
            if any(c in mode for c in "wax+"):
                audit["write_attempts"] += 1
                raise RuntimeError("Evaluation scoring must not write files or train models")
            return original(file, mode, *args, **kwargs)
        return open_file

    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket, "connect", deny_network))
        stack.enter_context(patch.object(socket, "create_connection", deny_network))
        stack.enter_context(patch.object(socket, "getaddrinfo", deny_network))
        stack.enter_context(patch.object(builtins, "open", guarded_open(original_open)))
        stack.enter_context(patch.object(io, "open", guarded_open(original_io_open)))
        yield


@contextmanager
def frozen_clock(at: datetime):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return at.astimezone(tz) if tz else at.replace(tzinfo=None)

    original_now = store_module.now
    with ExitStack() as stack:
        # Patch imported aliases in the actual scorer, rather than changing its
        # feature logic. Duration/age features see the trigger's timestamp.
        for name, module in list(sys.modules.items()):
            if module is None or not (name.startswith("core.") or name.startswith("packs.guard")):
                continue
            for attr, value in list(vars(module).items()):
                if value is datetime:
                    stack.enter_context(patch.object(module, attr, FrozenDateTime))
                elif value is original_now:
                    stack.enter_context(patch.object(module, attr, lambda: at))
        stack.enter_context(patch.object(datetime_module, "datetime", FrozenDateTime))
        yield


def replay(scenario: dict):
    """Load normal history and only the incident prefix through the trigger."""
    prefix = []
    for event in scenario["events"]:
        prefix.append(event)
        if event["event_id"] == scenario["trigger_event_id"]:
            break
    else:
        raise ValueError(f"{scenario['scenario_id']}: trigger missing")
    trigger = prefix[-1]
    at = store_module.parse(trigger["ts"])
    if any(store_module.parse(e["ts"]) > at for e in prefix):
        raise ValueError("scenario prefix contains future events")
    st = store_module.Store()
    path = ROOT / f"agent/packs/guard/data/history/{scenario['user_id']}.jsonl"
    history = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for event in history:
        if event["user_id"] != scenario["user_id"] or errors("Event", event):
            raise ValueError(f"invalid baseline Event in {path}")
        if store_module.parse(event["ts"]) <= at:
            events.ingest(st, copy.deepcopy(event))
    for event in prefix:
        events.ingest(st, copy.deepcopy(event))
    return st, copy.deepcopy(st.events[trigger["event_id"]]), at


def load_benign(path: Path) -> dict[str, dict]:
    """Separate controls become replay inputs, never frozen-split members."""
    data = json.loads(path.read_text())
    if data.get("format_version") != 1 or data.get("synthetic") is not True:
        raise ValueError("expected version 1 synthetic benign-text controls")
    records = data["records"]
    if not records or len({r["text_id"] for r in records}) != len(records):
        raise ValueError("benign controls must be nonempty with unique text IDs")
    if len({r["event"]["event_id"] for r in records}) != len(records):
        raise ValueError("benign control event IDs must be unique")
    rows = {}
    for record in records:
        event = record["event"]
        if record["label"] != "legit" or event["type"] != "message.forwarded" \
                or not event["data"].get("text") or errors("Event", event):
            raise ValueError(f"invalid benign control {record['text_id']}")
        key = f"benign_texts.json#{record['text_id']}"
        rows[key] = {"scenario_id": record["text_id"], "user_id": event["user_id"],
                     "label": "legit", "hard_negative": False,
                     "trigger_event_id": event["event_id"], "events": [event],
                     "generator": {"seed": 0, "variant": "benign_text_control"}}
    return rows


def evaluate(split: dict, rows: dict[str, dict], audit: dict, outputs=None):
    module, import_error = None, None
    try:
        module = importlib.import_module("packs.guard.ml")
    except ModuleNotFoundError as exc:
        if exc.name != "packs.guard.ml":
            import_error = f"{type(exc).__name__}: {exc.name}"
    except Exception as exc:
        import_error = type(exc).__name__
    active, baseline = outputs if outputs is not None else ([], [])
    for path in split["test"]:
        scenario = rows[path]
        violations = errors("DatasetScenario", scenario)
        if violations:
            raise ValueError(f"{path}: {violations}")
        at = store_module.parse(next(e["ts"] for e in scenario["events"]
                                    if e["event_id"] == scenario["trigger_event_id"]))
        for name, fn, output in (("rules", toolbox.rules_score, baseline), ("brain", toolbox.score, active)):
            route = {"ml_called": False, "ml_error": None, "ml_returned_score": False}
            original = getattr(module, "score", None) if module else None

            def observed(*args, **kwargs):
                route["ml_called"] = True
                try:
                    value = original(*args, **kwargs)
                    route["ml_returned_score"] = isinstance(value, dict) and bool(value.get("threat"))
                    return value
                except Exception as exc:
                    route["ml_error"] = type(exc).__name__
                    raise

            with frozen_clock(at), ExitStack() as stack:
                if name == "brain" and original:
                    stack.enter_context(patch.object(module, "score", observed))
                st, trigger, _ = replay(scenario)
                # Labels, hard_negative and generator.variant never reach fn.
                prediction = fn(st, scenario["user_id"], trigger)
            violations = errors("RiskScore", prediction)
            if violations:
                raise ValueError(f"{scenario['scenario_id']}/{name}: invalid RiskScore {violations}")
            output.append({"scenario_id": scenario["scenario_id"], "path": path,
                           "label": scenario["label"], "hard_negative": scenario["hard_negative"],
                           "variant": scenario["generator"]["variant"],
                           "trigger_type": trigger["type"],
                           "prediction": prediction, "route": route})
    if any(audit.values()):
        raise RuntimeError(f"scorer attempted side effects: {audit}")
    return active, baseline, {"module_present": module is not None, "import_error": import_error}


def percent(value):
    return "N/A" if value is None else f"{100 * value:.1f}%"


def final_model_ready(model_status: dict, rows: list[dict]) -> bool:
    return bool(rows) and model_status["module_present"] and not model_status["import_error"] \
        and all(row["route"]["ml_called"] and not row["route"]["ml_error"]
                and row["route"].get("ml_returned_score")
                and (not row["prediction"]["model"].lower().startswith("rules")
                     or row.get("trigger_type") == "message.forwarded") for row in rows) \
        and any(not row["prediction"]["model"].lower().startswith("rules") for row in rows)


def independent_split(split_sha256: str, audit: dict) -> bool:
    return not (audit.get("status") == "test_informed"
                and audit.get("affected_split_sha256") == split_sha256)


def report(result: dict) -> str:
    meta, active, baseline = result["provenance"], result["brain"], result["rules"]
    lines = ["# Titan development evaluation", "", f"Mode: **{meta['mode']}**.", "",
             "Presentation status: **test-informed during development; provisional, no headline claim**.", "",
             "D-053/D-053a reserve Devpost/video headline numbers for the single sealed run in sealed_run/results.md. These original-split results remain development evidence even with a model present.", "",
             f"Model training audit: **{result['training_audit'].get('status', 'not recorded')}**. {result['training_audit'].get('reason', '')} See model_audit.md and D-053.", "",
             f"Scorer source on main: `{meta['main_commit']}`. Evaluation checkout: `{meta['evaluation_commit']}`.",
             f"Dataset SHA-256: `{meta['dataset_sha256']}`. Split SHA-256: `{meta['split_sha256']}`.",
             f"Scored {len(result['predictions'])} test cases; train={meta['train_count']}, test={meta['test_count']}. All 36 hard negatives and the entire code_relay family are held out.",
             "", "## Per-threat results", "",
             "Exact class, one versus rest, using the returned threat label without threshold tuning. Precision = TP/(TP+FP); recall = TP/(TP+FN); FPR = FP/(FP+TN). N/A means a zero denominator.", "",
             "| Threat | Support | Rules precision | Brain precision | Rules recall | Brain recall | Rules FPR | Brain FPR |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for label, row in active["per_threat"].items():
        before = baseline["per_threat"][label]
        lines.append(f"| {label} | {row['support']} | {percent(before['precision'])} | {percent(row['precision'])} | {percent(before['recall'])} | {percent(row['recall'])} | {percent(before['false_positive_rate'])} | {percent(row['false_positive_rate'])} |")
    lines += ["", "## Hard negatives and code relay", "",
              "| Slice | Support | Rules | Brain |", "|---|---:|---:|---:|",
              f"| Legit hard-negative false-alert rate (any non-legit prediction) | {active['hard_negatives']['support']} | {percent(baseline['hard_negatives']['false_positive_rate'])} | {percent(active['hard_negatives']['false_positive_rate'])} |",
              f"| Code-relay coached recall | {active['code_relay']['support']} | {percent(baseline['code_relay']['recall'])} | {percent(active['code_relay']['recall'])} |", "",
              "Code relay is part of coached (D-031). The subtype has no distinct predicted label, so no subtype precision is invented. Only eight ordinary legit cases remain in train after all hard-negative variant families are reserved for test.", ""]
    controls = result["benign_texts"]
    lines += ["## Separate benign forwarded-text controls", "",
              "These evaluation-only controls are outside the frozen development split and are never used for training or tuning. Scam-text FPR = number predicted scam_text / number of benign texts; any other threat prediction is also shown as a false alert.", "",
              "| Scorer | Benign texts | Scam-text false positives | Scam-text FPR | Any-threat false alerts | Any-threat false-alert rate |",
              "|---|---:|---:|---:|---:|---:|"]
    for name in ("rules", "brain"):
        row = controls[name]
        lines.append(f"| {name} | {row['support']} | {row['scam_text_false_positives']} | {percent(row['scam_text_false_positive_rate'])} | {row['any_nonlegit_false_alerts']} | {percent(row['any_nonlegit_false_alert_rate'])} |")
    lines += ["", f"Benign controls SHA-256: `{controls['sha256']}`; source commit: `{controls['source_commit']}`; present on fetched main: `{controls['on_main']}`.",
              "Ten hand-written synthetic notices are a small control set, not representative benign-text validation.", "",
              "## Confidence and observed correctness", "",
              "Returned confidence bands versus exact-class accuracy on the frozen test set (including the D-051 recovery mapping), excluding separate benign controls. The mean scalar is the scorer's returned probability: the rules use it as threat risk even for a legit prediction, so it is not uniformly a predicted-class posterior. This table is descriptive; no calibrated-probability claim, ECE, or Brier score is inferred from the rules.", "",
              "| Scorer | Band | Cases | Mean returned probability | Actual exact-class accuracy | Marked calibrated |", "|---|---|---:|---:|---:|---:|"]
    for name, summary in (("rules", baseline), ("brain", active)):
        for band, row in summary["calibration"].items():
            lines.append(f"| {name} | {band} | {row['support']} | {percent(row['mean_probability'])} | {percent(row['exact_class_accuracy'])} | {row['calibrated_count']} |")
    lines += ["", "## Mode and limitations", "",
              f"Brain RiskScore.model counts: `{json.dumps(active['model_counts'], sort_keys=True)}`.",
              f"ML import/route status: `{json.dumps(result['model_status'], sort_keys=True)}`. Captured scorer exceptions: `{json.dumps(meta['fallback_errors'], sort_keys=True)}`.",
              f"Blocked network attempts: {meta['audit']['network_attempts']}; blocked file writes: {meta['audit']['write_attempts']}; blocked labeled-scenario reads: {meta['audit'].get('scenario_read_attempts', 0)}.",
              "The baseline is core.toolbox.rules_score unchanged; the brain column calls core.toolbox.score, which selects the ML implementation automatically when present. Identical rules columns do not demonstrate model improvement.",
              f"D-051 maps all {active['recovery_scam']['support']} recovery_scam cases into exact-class metrics: call-based triggers are coached; message.forwarded is scam_text. Original dataset labels and the split are unchanged. Their mapped accuracy is {percent(active['recovery_scam']['mapped_exact_class_accuracy'])}; predicted labels: `{json.dumps(active['recovery_scam']['predicted_labels'], sort_keys=True)}`.",
              "Each case uses a fresh Store, only its user's pre-trigger baseline and incident prefix, and time frozen at the trigger. Later attacker logins are excluded. Whole variants remain disjoint in the frozen split, whose fingerprint is checked before scoring. The model was tuned after inspecting this development set; the scorer receives no labels during this run.",
              "These are small, synthetic, generator-held-out results. They do not establish performance on real carrier data. The primary per-class FPR across all scenario types and the separate benign-text FPR measure different negative populations.",
              "", "## Development commands", "", "```bash", "python3 evals/build_split.py --check", "python3 evals/run.py", "# Require an installed model, still development evidence:", "python3 evals/run.py --require-model", "```", "",
              "Machine-readable scores, confusion counts, histories/scorer/model hashes, and fallback routing are in results.json.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-model", action="store_true")
    parser.add_argument("--sealed", action="store_true", help="consume the single frozen-model sealed attempt")
    parser.add_argument("--sealed-manifest", type=Path,
                        default=ROOT / "agent/packs/guard/data/sealed/manifest.json")
    parser.add_argument("--freeze", type=Path, default=OUT / "frozen_model.json")
    parser.add_argument("--benign-texts", type=Path, default=BENIGN_TEXTS,
                        help="separate control file; defaults to the data file on main")
    args = parser.parse_args()
    if args.sealed:
        if __package__:
            from . import sealed
        else:
            import sealed
        sealed.execute(args, sys.modules[__name__])
        return
    split = json.loads(SPLIT.read_text())
    rows = validate(split)
    if git("diff", "origin/main", "--", "agent"):
        raise RuntimeError("Scorer/data differ from fetched main; rebase onto origin/main first")
    untracked = git("ls-files", "--others", "--exclude-standard", "--", "agent")
    tracked_on_main = set(git("ls-tree", "-r", "--name-only", "origin/main", "--", "agent").splitlines())
    model_paths = list((ROOT / "agent/packs/guard/ml").rglob("*"))
    local_model_files = {p.relative_to(ROOT).as_posix() for p in model_paths
                         if p.is_file() and "__pycache__" not in p.parts and not p.name.startswith(".")}
    if untracked or local_model_files - tracked_on_main:
        raise RuntimeError("Untracked scorer/model files are not evidence for a scorer on main: "
                           + str(untracked or sorted(local_model_files - tracked_on_main)))
    benign_path = args.benign_texts.resolve()
    if not benign_path.is_file():
        raise RuntimeError("Benign controls are not in this checkout yet; merge/rebase the lane/data PR "
                           "or supply its file with --benign-texts for a provisional run")
    benign_rows = load_benign(benign_path)
    benign_repo_path = "agent/packs/guard/data/benign_texts.json"
    benign_on_main = benign_repo_path in tracked_on_main and hashlib.sha256(
        subprocess.check_output(["git", "show", f"origin/main:{benign_repo_path}"], cwd=ROOT)
    ).hexdigest() == file_hash(benign_path)
    benign_commit = committed_source(benign_path)
    audit = {"network_attempts": 0, "write_attempts": 0, "scenario_read_attempts": 0}
    with offline_read_only(audit, (benign_path,)):
        active, baseline, model_status = evaluate(split, rows, audit)
        benign_active, benign_rules, _ = evaluate({"test": list(benign_rows)}, benign_rows, audit)
    summary, rules = summarize(active), summarize(baseline)
    rule_names = lambda name: name.lower().startswith("rules")
    names = summary["model_counts"]
    actual_model = any(not rule_names(name) for name in names)
    mode = ("hybrid model and rules" if actual_model and any(rule_names(n) for n in names)
            else "model" if actual_model else "rules only (model rerun pending)")
    ready = actual_model and final_model_ready(model_status, active + benign_active) and benign_on_main
    if args.require_model and not ready:
        raise RuntimeError("Final run requires a model on every route without errors, and benign controls on main")
    training_audit = json.loads(OUT.joinpath("model_audit.json").read_text())
    agent = ROOT / "agent"
    scorer_paths = list((agent / "core").glob("*.py")) + list((agent / "packs/guard").glob("*.py"))
    result = {"provenance": {
        "mode": mode, "final_model_run": False,
        "evaluation_role": "test-informed during development",
        "main_commit": git("rev-parse", "origin/main"),
        "evaluation_commit": git("rev-parse", "HEAD"), "dataset_sha256": split["dataset"]["sha256"],
        "split_sha256": file_hash(SPLIT), "train_count": len(split["train"]), "test_count": len(split["test"]),
        "scorer_hashes": hashes(scorer_paths), "model_hashes": hashes(model_paths),
        "evaluation_hashes": hashes(OUT.glob("*.py")), "python": sys.version,
        "history_hashes": hashes((agent / "packs/guard/data/history").glob("*.jsonl")),
        "personas_sha256": file_hash(agent / "packs/guard/data/personas.json"),
        "audit": audit, "fallback_errors": dict(Counter(r["route"]["ml_error"] for r in active + benign_active if r["route"]["ml_error"]))},
        "model_status": model_status, "training_audit": training_audit,
        "brain": summary, "rules": rules,
        "benign_texts": {"sha256": file_hash(benign_path), "source_commit": benign_commit,
                         "on_main": benign_on_main, "brain": benign_summary(benign_active),
                         "rules": benign_summary(benign_rules)},
        "benign_predictions": benign_active, "benign_rules_predictions": benign_rules,
        "predictions": active, "rules_predictions": baseline}
    OUT.joinpath("results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    markdown = report(result)
    OUT.joinpath("results.md").write_text(markdown)
    print(markdown)


if __name__ == "__main__":
    main()
