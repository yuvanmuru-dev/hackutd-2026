"""Freeze a variant-disjoint evaluation split before observing predictions."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "agent/packs/guard/data/scenarios"
SPLIT = Path(__file__).with_name("split.json")

# Selected by attack style before running any scorer. D-031 puts the entire
# code_relay family in test so its separate result is genuinely held out.
HELD_OUT = {
    "pin_failure_before_swap", "remote_care_sim_swap",       # takeover
    "code_relay", "unverified_care_port_out",                # coached
    "lookalike_refund", "code_request_no_link",              # forwarded text
    "rotating_regions",                                    # bot
    "recovery_call_account_code", "recovery_text_unlock",    # recovery scam
}


def dataset() -> dict[str, dict]:
    return {p.relative_to(ROOT).as_posix(): json.loads(p.read_text())
            for p in sorted(SCENARIOS.glob("*.json"))}


def fingerprint(rows: dict[str, dict]) -> str:
    digest = hashlib.sha256()
    for path in sorted(rows):
        digest.update(path.encode() + b"\0" + (ROOT / path).read_bytes() + b"\0")
    return digest.hexdigest()


def validate(split: dict, rows: dict[str, dict] | None = None) -> dict[str, dict]:
    rows = dataset() if rows is None else rows
    train, test = split["train"], split["test"]
    if len(train) != len(set(train)) or len(test) != len(set(test)):
        raise ValueError("duplicate paths in split")
    if set(train) & set(test) or set(train) | set(test) != set(rows):
        raise ValueError("split must partition every dataset file exactly once")
    train_variants = {rows[p]["generator"]["variant"] for p in train}
    test_variants = {rows[p]["generator"]["variant"] for p in test}
    if train_variants & test_variants:
        raise ValueError("generator.variant leakage across train/test")
    if any(rows[p]["hard_negative"] for p in train):
        raise ValueError("all hard negatives must be in test")
    if split["dataset"]["sha256"] != fingerprint(rows):
        raise ValueError("dataset changed after split was frozen; do not silently resplit")
    if not train or not test:
        raise ValueError("both partitions must be nonempty")
    return rows


def build() -> dict:
    rows = dataset()
    variants = {s["generator"]["variant"] for s in rows.values()}
    missing = HELD_OUT - variants
    if missing:
        raise ValueError(f"held-out variants absent: {sorted(missing)}")
    hard_variants = {s["generator"]["variant"] for s in rows.values() if s["hard_negative"]}
    test_variants = HELD_OUT | hard_variants
    test = [p for p, s in rows.items() if s["generator"]["variant"] in test_variants]
    train = [p for p in rows if p not in set(test)]
    split = {
        "format_version": 1,
        "path_format": "repository_relative",
        "selection": "Whole generator.variant families; every hard-negative family in test; fixed before scoring.",
        "dataset": {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                    "sha256": fingerprint(rows), "scenarios": len(rows)},
        "held_out_variants": sorted(test_variants),
        "train_variants": sorted(variants - test_variants),
        "counts": {"train": dict(sorted(Counter(rows[p]["label"] for p in train).items())),
                   "test": dict(sorted(Counter(rows[p]["label"] for p in test).items())),
                   "test_hard_negatives": sum(rows[p]["hard_negative"] for p in test)},
        "train": train,
        "test": test,
    }
    validate(split, rows)
    return split


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate frozen split without rewriting it")
    args = parser.parse_args()
    split = json.loads(SPLIT.read_text()) if args.check else build()
    validate(split)
    if not args.check:
        SPLIT.parent.mkdir(parents=True, exist_ok=True)
        SPLIT.write_text(json.dumps(split, indent=2) + "\n")
    print(f"{'validated' if args.check else 'wrote'} split: train={len(split['train'])} test={len(split['test'])}")
    print(json.dumps(split["counts"], sort_keys=True))
    print("variant overlap=0; hard negatives in train=0")


if __name__ == "__main__":
    main()
