"""Fast gate: POST /check. Rules only (ML score plugs in later), no LLM, must answer in < 300 ms.

allow  - go ahead
pause  - show the pause screen first ("Are you on the phone with someone who asked you to do this?")
hold   - apply it, but on a 24 h hold (transfer PIN)
block  - don't apply; Titan steps in (customer tapped "help me", or clear takeover)
"""
from __future__ import annotations

from datetime import timedelta

from core.store import Store, iso, new_id, now

PAUSE_SCREEN = {
    "title": "Pause. Are you on the phone with someone who asked you to do this?",
    "body": "T-Mobile will never call and ask you to turn off protection or share a PIN. "
            "The call you're on right now is from a number we can't verify.",
    "help_label": "I'm on a call: help me",
    "continue_label": "I'm doing this on my own",
}


def _last_login(store: Store, uid: str) -> dict | None:
    logins = [e for e in store.events.values() if e["user_id"] == uid and e["type"] == "login"]
    return max(logins, key=lambda e: e["ts"]) if logins else None


def check(store: Store, req: dict) -> dict:
    uid, action = req["user_id"], req["action"]
    call = store.active_call(uid)
    suspicious = store.suspicious(call)
    summary = store.call_summary(call)
    reasons: list[str] = []
    decision = "allow"
    hold_until = None
    pause = None
    face = req.get("face")
    face_ok = bool(face and face["match"] and face["liveness"] >= 0.8 and face["antispoof"] >= 0.8)

    if suspicious:
        mins = summary["duration_s"] // 60
        reasons.append(f"Unverified call active for {mins} min")
        if call["caller_name"] and "t-mobile" in call["caller_name"].lower():
            reasons.append("Caller ID claims to be T-Mobile")

    if action == "protection_off":
        if suspicious:
            reasons.append("Turning off a protection during that call")
            choice = req.get("customer_choice")
            if choice == "on_call_help":
                decision = "block"
            elif choice == "doing_it_myself" and (face_ok or not store.users[uid]["face_enabled"]):
                decision = "allow"
                reasons.append("Customer chose to continue; Titan keeps watching this call")
            else:
                decision, pause = "pause", PAUSE_SCREEN
    elif action == "transfer_pin":
        if suspicious:
            decision = "hold"
            hold_until = iso(now() + timedelta(hours=24))
            reasons.append("Transfer PIN requested during an unverified call")
    elif action in ("sim_swap", "change_email", "change_password", "add_line"):
        last = _last_login(store, uid)
        if last and last["data"].get("new_device"):
            decision = "hold"
            hold_until = iso(now() + timedelta(hours=24))
            reasons.append(f"Signed in from a new device ({last['data'].get('region', 'unknown area')})")
        elif suspicious:
            decision, pause = "pause", PAUSE_SCREEN
            reasons.append("Sensitive change during that call")

    if decision == "allow" and not reasons:
        reasons.append("No active suspicious call")

    result = {"check_id": new_id("chk"), "decision": decision, "reasons": reasons, "during_call": bool(call),
              "call": summary, "risk": None, "case_id": store.case_by_call.get(call["call_id"]) if call else None,
              "hold_until": hold_until, "pause_screen": pause}
    store.checks[result["check_id"]] = {"user_id": uid, "action": action, "decision": decision}
    return result
