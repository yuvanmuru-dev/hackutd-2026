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

    # pre-freeze probe cases (D-053a): invented events, each a defect an adversarial review reproduced
    def ev(i, typ, when, **d):
        e = {"event_id": f"p{i}", "user_id": "usr_maya", "type": typ, "ts": when, "source": "generator", "data": d}
        if "call_id" in d:
            e["call_id"] = d.pop("call_id")
        return e
    region = ev(1, "line.region", "2026-11-07T15:59:59Z", region="Dallas, TX")
    hers = ev(2, "login", "2026-11-07T16:00:00Z", device_hash="h_maya_laptop", region="Dallas, TX", new_device=False, succeeded=True)
    stray = ev(3, "login", "2026-11-07T16:03:00Z", device_hash="h_random", region="Seattle, WA", new_device=True, succeeded=False)
    h = [region, hers, stray, ev(4, "protection.changed", "2026-11-07T16:05:00Z", name="sim_protection", enabled=True, via="portal")]
    check("stray failed login, then she turns a protection on", score("usr_maya", h[-1], h), "legit")
    bad = ev(5, "login", "2026-11-07T16:00:00Z", device_hash="h_bad", region="Lagos, NG", new_device=True, succeeded=True)
    h = [region, bad, ev(6, "login", "2026-11-07T16:02:00Z", device_hash="h_maya_laptop", region="Dallas, TX", new_device=False, succeeded=True),
         ev(7, "sim_swap.requested", "2026-11-07T16:05:00Z", new_device_hash="h_bad", channel="app")]
    check("attacker's login masked by her later login, swap to attacker's device", score("usr_maya", h[-1], h), "takeover", 0.8)
    h = [ev(8, "sim_swap.requested", "2026-11-07T16:05:00Z", new_device_hash="h_unknown", channel="care")]
    check("remote swap to a never-seen device, no region clue", score("usr_maya", h[-1], h), "takeover", 0.5)
    h = [ev(9, "sim_swap.requested", "2026-11-07T16:05:00Z", new_device_hash="h_unknown", channel="store")]
    check("store swap to a new device", score("usr_maya", h[-1], h), "legit")
    h = [region, *[ev(10 + i, "login", f"2026-11-07T16:0{i}:00Z", device_hash="h_maya_laptop", region="Dallas, TX", new_device=False, succeeded=False) for i in range(3)],
         ev(13, "login", "2026-11-07T16:04:00Z", device_hash="h_maya_laptop", region="Dallas, TX", new_device=False, succeeded=True)]
    check("three failed sign-ins from her own device at home", score("usr_maya", h[-1], h), "legit")
    scam_call = ev(14, "call.started", "2026-11-07T16:00:00Z", call_id="c1", direction="in", other_number_hash="x",
                   caller_name="T-Mobile Support", attestation="C", seen_before=False, scam_label=True)
    h = [scam_call, ev(15, "call.ended", "2026-11-07T16:18:00Z", call_id="c1"), ev(16, "transfer_pin.requested", "2026-11-07T16:20:00Z", channel="portal")]
    check("scammer hangs up, transfer PIN requested 2 minutes later", score("usr_maya", h[-1], h), "coached", 0.8)
    h = [scam_call, ev(17, "login", "2026-11-07T16:05:00Z", device_hash="h_maya_laptop", region="Dallas, TX", new_device=False, succeeded=True)]
    check("unverified call with nothing sensitive done", score("usr_maya", h[-1], h), "legit")
    # demo path: the live trigger is stamped now() while the fixture call.started is hours older; the call must still count
    h = [scam_call, ev(18, "transfer_pin.requested", "2026-11-08T05:00:00Z", channel="portal")]
    check("fixture call hours before a live transfer PIN request", score("usr_maya", h[-1], h), "coached", 0.8)
    for want, text in [("legit", "T-Mobile: your verification code is 482913. Don't share this code with anyone."),
                       ("legit", "Zelle: You received $40.00 from Ana."),
                       ("legit", "Wells Fargo: your wire transfer of $1,200 was completed."),
                       ("legit", "Mom what's the garage code again?"),
                       ("legit", "Bill ready: https://www.tmobile.com/bill"),
                       ("scam_text", "Account alert: please provide the one time code to keep service on."),
                       ("scam_text", "Reply with the c0de we sent"),
                       ("scam_text", "Wire $300 today or lose your number"),
                       ("scam_text", "Pay your balance with Apple gift cards to avoid suspension"),
                       ("scam_text", "Verify: http://tmoblie.com/secure")]:
        check(f"text: {text[:40]}", score_text(text), want)

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
