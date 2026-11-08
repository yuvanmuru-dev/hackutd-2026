"""Pure-Python inference for the exported XGBoost model (no numpy, no xgboost at serve time).

models/risk.json: {"classes": [...], "features": [...], "base_score": [...], "trees": [{"class": k, "tree": <dump node>}]}
Each dump node is xgboost's get_dump(dump_format="json", with_stats=True) output; internal node values
(cover-weighted means of their leaves) are precomputed by train.py as "v" so path attributions are O(depth).
models/calib.json: {"method": "isotonic", "x": [...], "y": [...], "n": int} or {"method": "none"}.
"""
from __future__ import annotations

import bisect
import json
import math
from functools import lru_cache
from pathlib import Path

MODELS = Path(__file__).resolve().parent / "models"


@lru_cache(maxsize=1)
def load() -> tuple[dict, dict] | None:
    risk, calib = MODELS / "risk.json", MODELS / "calib.json"
    if not risk.exists():
        return None
    model = json.loads(risk.read_text(encoding="utf-8"))
    cal = json.loads(calib.read_text(encoding="utf-8")) if calib.exists() else {"method": "none"}
    model["_index"] = {f: i for i, f in enumerate(model["features"])}
    return model, cal


def _walk(node: dict, x: list[float], index: dict, contrib: list[float]) -> float:
    """Leaf value for x; adds each split's change in expected value to its feature (Saabas)."""
    while "leaf" not in node:
        i = index[node["split"]]
        val = x[i]
        nxt = node["missing"] if val is None or (isinstance(val, float) and math.isnan(val)) else (
            node["yes"] if val < node["split_condition"] else node["no"])
        child = next(c for c in node["children"] if c["nodeid"] == nxt)
        contrib[i] += child.get("v", child.get("leaf", 0.0)) - node["v"]
        node = child
    return node["leaf"]


def predict(x: list[float]) -> tuple[list[float], list[list[float]], dict, dict] | None:
    """Returns (softmax probs per class, per-class feature contributions in margin space, model, calib)."""
    loaded = load()
    if loaded is None:
        return None
    model, cal = loaded
    k, idx = len(model["classes"]), model["_index"]
    margins = list(model["base_score"])
    contrib = [[0.0] * len(model["features"]) for _ in range(k)]
    for t in model["trees"]:
        c = t["class"]
        margins[c] += _walk(t["tree"], x, idx, contrib[c])
    m = max(margins)
    exps = [math.exp(v - m) for v in margins]
    s = sum(exps)
    return [e / s for e in exps], contrib, model, cal


def calibrate(p: float, cal: dict) -> tuple[float, bool]:
    if cal.get("method") != "isotonic" or not cal.get("x"):
        return p, False
    xs, ys = cal["x"], cal["y"]
    if p <= xs[0]:
        return ys[0], True
    if p >= xs[-1]:
        return ys[-1], True
    j = bisect.bisect_right(xs, p)
    x0, x1, y0, y1 = xs[j - 1], xs[j], ys[j - 1], ys[j]
    return (y0 + (y1 - y0) * (p - x0) / (x1 - x0) if x1 > x0 else y0), True
