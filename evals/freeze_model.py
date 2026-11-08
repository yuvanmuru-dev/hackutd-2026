"""Record the D-053a model freeze without importing or executing the scorer."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FREEZE = Path(__file__).with_name("frozen_model.json")
NOT_BEFORE = "2026-11-08T06:30:00+00:00"  # T+12, 00:30 Chicago (D-053a)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def aggregate(hashes: dict[str, str]) -> str:
    return sha(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode())


def serving_path(path: str) -> bool:
    p = Path(path)
    if "__pycache__" in p.parts or any(part.startswith(".") for part in p.parts):
        return False
    return ((p.parent.as_posix() in ("agent/core", "agent/packs/guard") and p.suffix == ".py")
            or path.startswith("agent/packs/guard/ml/"))


def input_path(path: str) -> bool:
    return (path in ("contracts/schema.json", "agent/requirements.txt")
            or path.startswith("contracts/fixtures/")
            or path.startswith("agent/packs/guard/data/history/")
            or path in ("agent/packs/guard/data/personas.json",
                        "agent/packs/guard/data/synthetic_registry.json"))


def _hashes_at(commit: str, paths: list[str]) -> dict[str, str]:
    return {p: sha(subprocess.check_output(["git", "show", f"{commit}:{p}"], cwd=ROOT))
            for p in paths}


def build_snapshot(commit: str, model_head: str) -> dict:
    """Both SHAs must be explicit, fetched, and connected by the PR merge."""
    if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (commit, model_head)):
        raise ValueError("Use full 40-character merge and final PR-head commit SHAs")
    if subprocess.run(["git", "merge-base", "--is-ancestor", commit, "origin/main"],
                      cwd=ROOT, check=False).returncode:
        raise ValueError("Freeze commit must be on fetched origin/main")
    parents = git("show", "-s", "--format=%P", commit).split()
    if len(parents) != 2 or parents[1] != model_head:
        raise ValueError("Expected PR #57 merge with its final head as second parent")
    paths = git("ls-tree", "-r", "--name-only", commit).splitlines()
    serving = _hashes_at(commit, [p for p in paths if serving_path(p)])
    model = {p: h for p, h in serving.items() if p.startswith("agent/packs/guard/ml/")}
    if "agent/packs/guard/ml/__init__.py" not in model or not any(
            p.startswith("agent/packs/guard/ml/models/") for p in model):
        raise ValueError("Freeze requires the real ML source and model artifacts")
    snapshot = {"format_version": 1, "decision": "D-053/D-053a", "pull_request": 57,
                "model_commit": commit, "model_head_commit": model_head, "parents": parents,
                "not_before_utc": NOT_BEFORE, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
                "serving_hashes": serving, "input_hashes": _hashes_at(commit, [p for p in paths if input_path(p)]),
                "model_hashes": model, "model_sha256": aggregate(model)}
    verify_snapshot(snapshot)
    return snapshot


def verify_snapshot(snapshot: dict) -> None:
    """Compare executable inputs to the frozen git blobs, not moving main."""
    if snapshot.get("format_version") != 1 or snapshot.get("pull_request") != 57:
        raise ValueError("Unrecognized model freeze")
    if snapshot.get("not_before_utc") != NOT_BEFORE:
        raise ValueError("Freeze must retain D-053a's tuning deadline")
    if datetime.now(timezone.utc) < datetime.fromisoformat(NOT_BEFORE):
        raise ValueError("D-053a tuning window remains open; do not freeze or score yet")
    commit, head = snapshot["model_commit"], snapshot["model_head_commit"]
    parents = git("show", "-s", "--format=%P", commit).split()
    if parents != snapshot["parents"] or len(parents) != 2 or parents[1] != head:
        raise ValueError("Freeze merge/head metadata does not match git")
    if subprocess.run(["git", "merge-base", "--is-ancestor", commit, "origin/main"],
                      cwd=ROOT, check=False).returncode:
        raise ValueError("Frozen merge is not on fetched origin/main")
    paths = git("ls-tree", "-r", "--name-only", commit).splitlines()
    for key, selected in (("serving_hashes", serving_path), ("input_hashes", input_path)):
        expected = _hashes_at(commit, [p for p in paths if selected(p)])
        if snapshot[key] != expected:
            raise ValueError(f"Freeze {key} differ from frozen git blobs")
        for p, digest in expected.items():
            if not (ROOT / p).is_file() or sha((ROOT / p).read_bytes()) != digest:
                raise ValueError(f"Runtime differs from frozen commit: {p}")
    actual = {p.relative_to(ROOT).as_posix() for p in (ROOT / "agent").rglob("*")
              if p.is_file() and serving_path(p.relative_to(ROOT).as_posix())}
    if actual != set(snapshot["serving_hashes"]):
        raise ValueError("Unexpected serving files outside the frozen snapshot")
    model = {p: h for p, h in snapshot["serving_hashes"].items()
             if p.startswith("agent/packs/guard/ml/")}
    if model != snapshot["model_hashes"] or aggregate(model) != snapshot["model_sha256"]:
        raise ValueError("Model aggregate/hash map mismatch")


def write_freeze(snapshot: dict, path: Path = FREEZE) -> None:
    # Exclusive creation is deliberate: no --force/update option exists.
    with path.open("x") as stream:
        stream.write(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True, help="verified PR #57 merge SHA")
    parser.add_argument("--model-head", required=True, help="verified final PR #57 head SHA")
    args = parser.parse_args()
    if FREEZE.exists():
        raise SystemExit("Freeze already exists; preserve it rather than replacing it")
    snapshot = build_snapshot(args.commit, args.model_head)
    write_freeze(snapshot)
    print(f"Frozen model commit: {snapshot['model_commit']}")
    print(f"Model SHA-256: {snapshot['model_sha256']}")


if __name__ == "__main__":
    main()
