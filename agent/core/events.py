"""Event ingest: store the event, track call windows, decide whether it triggers a run.

Triggers (docs/ARCHITECTURE.md):
  call.started, unverified, caller ID says T-Mobile  -> heads-up text (case per call)
  transfer_pin.requested during a suspicious call    -> coached run
  otp.sent during a suspicious call                  -> coached run (code relay)
  sim_swap.requested after a new-device login        -> takeover run
  message.forwarded                                  -> scam_text run
"""
from __future__ import annotations

from core.store import Store, iso, now


def _case_for_call(store: Store, uid: str, call_id: str, title: str) -> dict:
    cid = store.case_by_call.get(call_id)
    return store.cases[cid] if cid else store.new_case(uid, title, call_id)


def ingest(store: Store, ev: dict) -> dict:
    """Returns {"duplicate", "case_id", "trigger"}; trigger is one of None, heads_up, coached, takeover, scam_text."""
    if ev["event_id"] in store.events:
        return {"duplicate": True, "case_id": None, "trigger": None}
    uid, typ = ev["user_id"], ev["type"]
    call = store.active_call(uid)
    if typ != "call.started" and not ev.get("call_id") and call:
        ev["call_id"] = call["call_id"]  # stamp actions taken during the call
    store.events[ev["event_id"]] = ev
    out = {"duplicate": False, "case_id": None, "trigger": None}

    if typ == "call.started":
        d = ev["data"]
        cid = ev.get("call_id") or f"call_{ev['event_id'][4:]}"
        ev["call_id"] = cid
        reported = d["other_number_hash"] in store.scam_numbers  # Titan reported it earlier: the network now labels it
        store.calls[cid] = {"call_id": cid, "user_id": uid, "caller_name": d.get("caller_name"), "attestation": d["attestation"],
                            "seen_before": d["seen_before"], "scam_label": d["scam_label"] or reported, "started_at": ev["ts"],
                            "ended_at": None, "other_number_hash": d["other_number_hash"]}
        c = store.calls[cid]
        if reported:
            case = _case_for_call(store, uid, cid, "Reported scam number calling again")
            out.update(case_id=case["case_id"], trigger="repeat_heads_up")
            return out
        if store.suspicious(c) and c["caller_name"] and "t-mobile" in c["caller_name"].lower():
            case = _case_for_call(store, uid, cid, "Unverified call claiming to be T-Mobile")
            out.update(case_id=case["case_id"], trigger="heads_up")
        return out

    if typ == "call.ended":
        c = store.calls.get(ev.get("call_id") or "") or call
        if c:
            c["ended_at"] = ev["ts"]
        return out

    if typ == "protection.changed" and ev["data"]["via"] != "titan":
        store.set_protection(uid, ev["data"]["name"], ev["data"]["enabled"])

    suspicious_call = call if store.suspicious(call) else None
    if typ in ("transfer_pin.requested", "otp.sent") and suspicious_call:
        case = _case_for_call(store, uid, suspicious_call["call_id"], "Coached during an unverified call")
        case["title"] = "Coached to turn off protection during a fake support call"
        out["case_id"] = case["case_id"]
        # Both real and mock runs emit this entry marker. Face checks and
        # other observational signals are not evidence that analysis ran.
        already_ran = any(s["stage"] == "trigger" and s["type"] == "plan" for s in case["steps"])
        if not case["run_running"] and not already_ran:
            out["trigger"] = "coached"
        return out

    if typ == "sim_swap.requested":
        logins = [e for e in store.events.values() if e["user_id"] == uid and e["type"] == "login"]
        if logins and max(logins, key=lambda e: e["ts"])["data"].get("new_device"):
            case = store.new_case(uid, "SIM swap right after a new-device login", None)
            out.update(case_id=case["case_id"], trigger="takeover")
        return out

    if typ == "message.forwarded":
        case = store.new_case(uid, "Forwarded text checked", None)
        out.update(case_id=case["case_id"], trigger="scam_text")
        return out

    if typ == "customer.reply" and ev["data"].get("case_id") in store.cases:
        case = store.cases[ev["data"]["case_id"]]
        case["messages"].append({"message_id": f"msg_{ev['event_id'][4:]}", "case_id": case["case_id"],
                                 "channel": ev["data"]["channel"] if ev["data"]["channel"] != "web" else "imessage",
                                 "direction": "in", "kind": "reply", "text": ev["data"]["text"], "ts": iso(now())})
        out["case_id"] = case["case_id"]
    return out
