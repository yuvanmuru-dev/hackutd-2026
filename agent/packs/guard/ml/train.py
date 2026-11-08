"""Offline trainer for the risk classifier. Trains ONLY on evals/split.json's train list (D-049, D-051).

Run from agent/:
  uv run --no-project --python 3.12 --with xgboost,scikit-learn,shap,numpy python packs/guard/ml/train.py

Writes models/risk.json (trees for pure-Python inference), models/calib.json (isotonic on out-of-fold
predictions), models/meta.json (split hash, counts, held-out variants, SHAP agreement). Prints a held-out
sanity check; the official numbers come from evals/run.py.
"""
from __future__ import annotations

import collections
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ML = Path(__file__).resolve().parent
AGENT = ML.parents[2]
REPO = AGENT.parent
sys.path.insert(0, str(AGENT))

import numpy as np  # noqa: E402
import shap  # noqa: E402
import xgboost as xgb  # noqa: E402
from sklearn.isotonic import IsotonicRegression  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402
from sklearn.utils.class_weight import compute_sample_weight  # noqa: E402

from packs.guard.ml import baselines  # noqa: E402
from packs.guard.ml.features import FEATURE_ORDER, build  # noqa: E402

CLASSES = ["takeover", "coached", "bot", "legit"]
HISTORY_TRIGGERS = ("login", "pin.attempt", "sim_swap.requested", "protection.changed")
PARAMS = dict(n_estimators=120, max_depth=3, learning_rate=0.1, subsample=0.9, colsample_bytree=0.9,
              objective="multi:softprob", num_class=len(CLASSES), reg_lambda=1.0, random_state=7, n_jobs=1)


def load_split() -> tuple[dict, bytes, str]:
    local = REPO / "evals" / "split.json"
    if local.exists():
        raw, src = local.read_bytes(), "evals/split.json"
    else:  # #55 not merged yet: read Yuvan's file from lane/evals, never a provisional split
        raw = subprocess.run(["git", "-C", str(REPO), "show", "origin/lane/evals:evals/split.json"],
                             capture_output=True, check=True).stdout
        src = "origin/lane/evals:evals/split.json"
    raw = raw.replace(b"\r\n", b"\n")  # hash the committed bytes, not a Windows autocrlf checkout
    split = json.loads(raw)
    if split.get("format_version") != 1 or not isinstance(split.get("train"), list):
        sys.exit(f"refusing to train: unexpected split format in {src}")
    return split, raw, src


def label_of(s: dict, trig: dict) -> str | None:
    lab = s["label"]
    if lab == "recovery_scam":  # D-051
        lab = "scam_text" if trig["type"] == "message.forwarded" else "coached"
    return None if lab == "scam_text" else lab  # scam texts belong to the text model


def scenario_rows(paths: list[str]) -> tuple[list, list, list, list]:
    X, y, groups, meta = [], [], [], []
    for p in paths:
        s = json.loads((REPO / p).read_text(encoding="utf-8"))
        trig = next(e for e in s["events"] if e["event_id"] == s["trigger_event_id"])
        lab = label_of(s, trig)
        if lab is None:
            continue
        x, _ = build(s["user_id"], trig, s["events"])
        X.append(x)
        y.append(CLASSES.index(lab))
        groups.append(s["generator"]["variant"])
        meta.append(s)
    return X, y, groups, meta


def history_rows() -> tuple[list, list, list]:
    """Legit negatives from each user's normal history (train has only 8 legit scenarios, D-051)."""
    X, y, groups = [], [], []
    for uid in baselines.personas().get("baselines", {}):
        hist = list(baselines.legit_history(uid))
        for e in hist:
            if e.get("type") in HISTORY_TRIGGERS:
                x, _ = build(uid, e, hist)
                X.append(x)
                y.append(CLASSES.index("legit"))
                groups.append(f"history_{uid}")
    return X, y, groups


def export_trees(booster: xgb.Booster) -> list[dict]:
    dumps = booster.get_dump(dump_format="json", with_stats=True)

    def annotate(node: dict) -> tuple[float, float]:
        if "leaf" in node:
            return node["leaf"], node["cover"]
        total = val = 0.0
        for c in node["children"]:
            v, cov = annotate(c)
            val += v * cov
            total += cov
        node["v"] = val / total if total else 0.0
        return node["v"], total

    def prune(node: dict) -> dict:
        keep = {k: node[k] for k in ("nodeid", "leaf", "split", "split_condition", "yes", "no", "missing", "v") if k in node}
        if "children" in node:
            keep["children"] = [prune(c) for c in node["children"]]
        return keep

    trees = []
    for i, d in enumerate(dumps):
        node = json.loads(d)
        annotate(node)
        trees.append({"class": i % len(CLASSES), "tree": prune(node)})
    return trees


def main() -> None:
    split, raw, src = load_split()
    test_set = set(split["test"])
    assert not set(split["train"]) & test_set, "train and test overlap"
    X, y, groups, meta = scenario_rows(split["train"])
    hn_in_train = [m["scenario_id"] for m in meta if m["hard_negative"]]
    assert not hn_in_train, f"hard negatives in train: {hn_in_train}"
    tv = {m["generator"]["variant"] for m in meta}
    test_variants = {json.loads((REPO / p).read_text(encoding="utf-8"))["generator"]["variant"] for p in split["test"]}
    assert not tv & test_variants, f"variant overlap: {tv & test_variants}"

    hX, hy, hg = history_rows()
    X, y, groups = np.array(X + hX, dtype=float), np.array(y + hy), groups + hg
    w = compute_sample_weight("balanced", y)
    print(f"train rows: {len(y)} ({len(hy)} legit history rows added) class counts {collections.Counter(CLASSES[i] for i in y)}")

    # out-of-fold predictions for calibration, grouped by generator variant so no fold sees its own family
    oof = np.zeros((len(y), len(CLASSES)))
    for tr, va in GroupKFold(n_splits=5).split(X, y, groups):
        m = xgb.XGBClassifier(**PARAMS)
        m.fit(X[tr], y[tr], sample_weight=w[tr])
        oof[va] = m.predict_proba(X[va])
    top = oof.max(axis=1)
    correct = (oof.argmax(axis=1) == y).astype(float)
    if len(y) >= 80:
        iso = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip").fit(top, correct)
        calib = {"method": "isotonic", "x": [round(float(v), 6) for v in iso.X_thresholds_],
                 "y": [round(float(v), 6) for v in iso.y_thresholds_], "n": int(len(y)),
                 "what": "P(predicted class is correct) from out-of-fold max class probability"}
    else:
        calib = {"method": "none", "n": int(len(y))}
    print(f"out-of-fold accuracy {correct.mean():.3f} on {len(y)} rows; calibration: {calib['method']}")

    model = xgb.XGBClassifier(**PARAMS)
    model.fit(X, y, sample_weight=w)
    booster = model.get_booster()
    booster.feature_names = FEATURE_ORDER
    trees = export_trees(booster)
    # base score per class = xgboost margin minus the sum of the leaves our walk visits (same row)
    from packs.guard.ml.infer import _walk
    idx = {f: i for i, f in enumerate(FEATURE_ORDER)}
    x0 = [float(v) for v in X[0]]
    leaf_sum = [0.0] * len(CLASSES)
    for t in trees:
        leaf_sum[t["class"]] += _walk(t["tree"], x0, idx, [0.0] * len(FEATURE_ORDER))
    margins = booster.predict(xgb.DMatrix(X[:1], feature_names=FEATURE_ORDER), output_margin=True)[0]
    base = [float(margins[k] - leaf_sum[k]) for k in range(len(CLASSES))]
    risk = {"classes": CLASSES, "features": FEATURE_ORDER, "base_score": base, "trees": trees}

    ML.joinpath("models").mkdir(exist_ok=True)
    (ML / "models" / "risk.json").write_text(json.dumps(risk, separators=(",", ":")), encoding="utf-8")
    (ML / "models" / "calib.json").write_text(json.dumps(calib, indent=1), encoding="utf-8")

    # held-out sanity check + parity (pure-Python vs xgboost) + reason agreement vs TreeSHAP
    import importlib
    from packs.guard.ml import infer
    importlib.reload(infer)
    tX, ty, _, tmeta = scenario_rows(split["test"])
    tX = np.array(tX, dtype=float)
    ref = model.predict_proba(tX)
    agree = parity = 0
    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(tX)
    sv = np.stack(sv, axis=-1) if isinstance(sv, list) else sv  # (n, features, classes)
    for i, x in enumerate(tX):
        probs, contrib, _, _ = infer.predict([float(v) for v in x])
        parity += int(np.allclose(probs, ref[i], atol=1e-4))
        k = int(np.argmax(probs))
        ours = set(np.argsort(-np.array(contrib[k]))[:3])
        theirs = set(np.argsort(-sv[i, :, k])[:3])
        agree += len(ours & theirs) / 3
    pred = ref.argmax(axis=1)
    print(f"pure-Python parity with xgboost: {parity}/{len(tX)}; top-3 reason agreement with TreeSHAP: {agree / len(tX):.0%}")
    print("held-out sanity (evals/run.py is the official number):")
    for k, c in enumerate(CLASSES):
        tp = int(((pred == k) & (np.array(ty) == k)).sum())
        fp = int(((pred == k) & (np.array(ty) != k)).sum())
        fn = int(((pred != k) & (np.array(ty) == k)).sum())
        print(f"  {c:9s} precision {tp / max(tp + fp, 1):.2f} recall {tp / max(tp + fn, 1):.2f} (n={int((np.array(ty) == k).sum())})")
    hn = [i for i, m in enumerate(tmeta) if m["hard_negative"]]
    print(f"  hard negatives predicted legit: {sum(int(pred[i] == CLASSES.index('legit')) for i in hn)}/{len(hn)}")

    meta_out = {
        "split_source": src, "split_sha256": hashlib.sha256(raw).hexdigest(),
        "dataset": split.get("dataset"), "train_scenarios_used": len(meta), "legit_history_rows": len(hy),
        "train_variants": sorted(tv), "held_out_variants": sorted(test_variants),
        "classes": CLASSES, "params": {k: v for k, v in PARAMS.items() if k != "n_jobs"},
        "calibration": {"method": calib["method"], "n": calib["n"]},
        "parity_with_xgboost": f"{parity}/{len(tX)}", "shap_top3_agreement": round(agree / len(tX), 3),
        "feature_revisions": [
            "Chosen after inspecting held-out failure families, so evals/run.py on this test set is optimistic for them:",
            "1. Call features gated on the call being unverified (raw on-a-call / call-minutes were generator shortcuts; training had no legit calls).",
            "2. SIM swap store channel added (in-store swaps need ID). A remote-swap feature was tried and dropped: it became the only takeover reason.",
            "3. Serving rule in __init__.py: a threat whose calibrated probability is < 0.5 does not fire when the rules see nothing (reported as legit).",
        ],
        "versions": {"xgboost": xgb.__version__, "shap": shap.__version__, "python": sys.version.split()[0]},
    }
    (ML / "models" / "meta.json").write_text(json.dumps(meta_out, indent=1), encoding="utf-8")
    print("wrote models/risk.json, calib.json, meta.json")


if __name__ == "__main__":
    main()
