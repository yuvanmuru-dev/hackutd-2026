"""Offline checks for packs.guard.ml. Run from agent/:  python packs/guard/ml/test_ml.py

Schema-valid RiskScore on the contract fixtures, the expected threats, the hard negative stays
legit, and score() stays under 100 ms.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

AGENT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(AGENT))

from core.contracts import errors, fixture  # noqa: E402
from packs.guard.ml import score, score_text  # noqa: E402


def check(name: str, out: dict, threat: str, min_p: float = 0.0) -> None:
    errs = errors("RiskScore", out)
    assert not errs, (name, errs)
    assert out["threat"] == threat, (name, out["threat"], out)
    assert out["probability"] >= min_p, (name, out["probability"])
    print(f"  ok {name}: {out['threat']} {out['probability']} {out['model']} · {out['top_reasons'][0]['text']}")


def trigger_and_history(scenario: dict) -> tuple[dict, list[dict]]:
    trig = next(e for e in scenario["events"] if e["event_id"] == scenario["trigger_event_id"])
    return trig, scenario["events"]


def main() -> None:
    t2 = fixture("scenario.t2.json")
    ev, hist = trigger_and_history(t2)
    check("T2 coached victim", score(t2["user_id"], ev, hist), "coached", 0.8)

    login, swap = fixture("event.t1_new_device_login.json"), fixture("event.t1_sim_swap.json")
    check("T1 takeover", score("usr_maya", swap, [login, swap]), "takeover", 0.8)

    t3 = fixture("event.t3_forwarded_text.json")
    check("T3 scam text via score()", score("usr_maya", t3, [t3]), "scam_text", 0.9)
    check("T3 scam text via score_text()", score_text(t3["data"]["text"]), "scam_text", 0.9)
    check("plain text", score_text("Dinner at 7? Love, Mom"), "legit")
    check("code request, no link", score_text("Account support: reply with the one-time login code we just sent."), "scam_text", 0.8)
    check("legit code mention", score_text("The garage code is 4471, see you Sunday"), "legit")
    check("empty text (screenshot only)", score_text(""), "legit")
    # D-052: pressure alone, or a link alone, is low "worth a look"; money rails are a scam
    check("urgency alone", score_text("Your bill is due. Act now to avoid a late fee in the app."), "legit")
    check("link alone", score_text("Your package shipped: https://track.example-carrier.com/abc"), "legit")
    check("urgent + unofficial link", score_text("Account suspended. Verify now: https://acct-help.net/x"), "scam_text", 0.7)
    check("money ask", score_text("To keep service on, buy two gift cards and send the numbers."), "scam_text", 0.8)
    check("official link", score_text("Your bill is ready: https://www.t-mobile.com/bill. Act now"), "legit")

    hn = fixture("scenario.hard_negative_daughter.json")
    ev, hist = trigger_and_history(hn)
    check("hard negative: long call with daughter", score(hn["user_id"], ev, hist), "legit")

    # reasons must be true for the case: T1 names the new device, the hard negative never claims one
    t1 = score("usr_maya", swap, [login, swap])
    feats = [r["feature"] for r in t1["top_reasons"]]
    assert "new_device" in feats or "region_mismatch" in feats, t1
    hn_out = score(hn["user_id"], *trigger_and_history(hn))
    assert all(r["feature"] not in ("new_device", "region_mismatch") or r["contribution"] <= 0 or hn_out["threat"] == "legit"
               for r in hn_out["top_reasons"]), hn_out
    if (AGENT / "packs/guard/ml/models/risk.json").exists():
        assert t1["model"] == "ml+rules", t1
        print(f"  ok model: ml+rules, calibrated={t1['calibrated']}, T1 reasons {[r['text'] for r in t1['top_reasons']]}")
        t2_out = score(t2["user_id"], *trigger_and_history(t2))
        print(f"  ok T2 reasons {[r['text'] for r in t2_out['top_reasons']]}")
        print(f"  ok hard negative reasons {[r['text'] for r in hn_out['top_reasons']]}")

    # history without the trigger, and out of order, must give the same answer
    ev, hist = trigger_and_history(t2)
    a = score(t2["user_id"], ev, list(reversed([e for e in hist if e["event_id"] != ev["event_id"]])))
    assert a["threat"] == "coached", a

    n, t0 = 300, time.perf_counter()
    for _ in range(n):
        score(t2["user_id"], ev, hist)
    per = (time.perf_counter() - t0) / n * 1000
    assert per < 100, per
    print(f"  ok latency: {per:.2f} ms per score()")
    print("PASS packs.guard.ml")


if __name__ == "__main__":
    main()
