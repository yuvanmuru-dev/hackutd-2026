"""Text commands Maya can send Titan by iMessage/SMS (D-062). Safer-only: a text can never turn a protection off,
create a transfer PIN or approve a looser change, because a SIM-swapped attacker receives her texts.

  STATUS  each protection on/off, the transfer PIN state, whether a case is open
  LOCK    turn every protection on and hold an active transfer PIN for 24 h
  HELP    what she can text

Every command is recorded where the dashboards look: the event timeline (protection.changed), the case thread
(her text + Titan's reply) and a step on the case, so the guardian screen and the portal show it live.
"""
from __future__ import annotations

import re

from core import outbound
from core.store import Store, iso, new_id, now, parse

COMMANDS = ("STATUS", "LOCK", "HELP")
NAMES = {"sim_protection": "SIM Protection", "port_out_protection": "Port Out Protection", "scam_block": "Scam Block"}


def match(ev: dict) -> str | None:
    """The command in a typed text, or None. Exact keyword only (no model), so a scam text can't trigger one."""
    if ev.get("type") not in ("customer.reply", "message.forwarded"):
        return None
    d = ev.get("data") or {}
    if d.get("image_url") or d.get("channel") not in ("imessage", "sms", "web"):
        return None
    word = re.sub(r"[^A-Za-z]", "", d.get("text") or "").upper()
    return word if word in COMMANDS else None


def _case(store: Store, ev: dict) -> dict:
    """Her open case if there is one (so it shows on that dashboard), else a small case for the command."""
    cid = (ev.get("data") or {}).get("case_id")
    if cid in store.cases and store.cases[cid]["status"] != "closed":
        return store.cases[cid]
    mine = [c for c in store.cases.values() if c["user_id"] == ev["user_id"] and c["status"] != "closed"]
    if mine:
        return max(mine, key=lambda c: c["updated_at"])
    case = store.new_case(ev["user_id"], "Maya texted Titan", None)
    case.update(status="watching", threat="legit", confidence="high")
    return case


def _pin_text(tp: dict) -> str:
    if tp["status"] == "held" and tp.get("hold_until"):
        return "held until " + parse(tp["hold_until"]).astimezone().strftime("%-I:%M %p")
    return {"none": "none requested", "active": "active"}.get(tp["status"], tp["status"])


def handle(store: Store, ev: dict, cmd: str) -> dict:
    if ev["event_id"] in store.events:
        return {"duplicate": True, "case_id": None, "trigger": None, "command": cmd}
    uid = ev["user_id"]
    store.events[ev["event_id"]] = ev
    case = _case(store, ev)
    run_id = new_id("run")
    case["messages"].append({"message_id": f"msg_{ev['event_id'][4:]}", "case_id": case["case_id"],
                             "channel": ev["data"]["channel"] if ev["data"]["channel"] != "web" else "imessage",
                             "direction": "in", "kind": "info", "text": ev["data"]["text"], "ts": iso(now())})
    store.add_step(case, run_id, "messaging", "watch", "message", f"Maya texted {cmd}", {"command": cmd})

    if cmd == "LOCK":
        turned_on = []
        for name, p in store.protections[uid].items():
            if not p["enabled"]:
                store.set_protection(uid, name, True)
                turned_on.append(NAMES[name])
                eid = new_id("evt")
                store.events[eid] = {"event_id": eid, "user_id": uid, "type": "protection.changed",
                                               "ts": iso(now()), "source": "messaging", "call_id": ev.get("call_id"),
                                               "data": {"name": name, "enabled": True, "via": "titan"}}
        held = store.transfer_pins[uid]["status"] == "active"
        if held:
            store.hold_transfer_pin(uid)
        did = ([f"turned on {', '.join(turned_on)}"] if turned_on else []) + (["held your transfer PIN for 24 hours"] if held else [])
        for what in turned_on:
            store.add_step(case, run_id, "response", "respond", "action", f"Turned {what} on (Maya texted LOCK)", {"command": cmd})
        if held:
            store.add_step(case, run_id, "response", "respond", "action", "Held the transfer PIN for 24 hours (Maya texted LOCK)", {"command": cmd})
        reply = (f"Titan: Locked. I {' and '.join(did)}." if did else "Titan: Everything was already locked.") + \
            " Every protection is on. Turning one off needs you signed in to your account, never a text."
    elif cmd == "STATUS":
        st = store.protection_state(uid)
        parts = [f"{NAMES[p['name']]}: {'on' if p['enabled'] else 'OFF'}" for p in st["protections"]]
        parts.append(f"Transfer PIN: {_pin_text(st['transfer_pin'])}")
        if st["shield_mode"]:
            parts.append("unverified call in progress")
        off = any(not p["enabled"] for p in st["protections"])
        reply = "Titan: " + " · ".join(parts) + "." + (" Text LOCK to turn everything on." if off else "")
    else:
        reply = ("Titan: Text STATUS to see your protections, LOCK to turn them all on, REPORT to report a scam call, "
                 "or forward me a suspicious text. T-Mobile will never ask you for a PIN or code by text.")

    msg = {"message_id": new_id("msg"), "case_id": case["case_id"], "channel": "imessage", "direction": "out",
           "kind": "info", "text": reply, "ts": iso(now())}
    case["messages"].append(msg)
    outbound.send_message(store, {"case_id": case["case_id"], "user_id": uid, "channel": "imessage", "kind": "info",
                                  "text": reply, "expects_reply": False, "action_id": None})
    store.add_step(case, run_id, "messaging", "reach", "message", f"Replied to {cmd}: \"{reply[7:90]}…\"", {"command": cmd})
    return {"duplicate": False, "case_id": case["case_id"], "trigger": None, "command": cmd}
