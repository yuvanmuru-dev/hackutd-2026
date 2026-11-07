"""Builds contracts/fixtures/* for contracts v0.3 so every file shares the same ids and times.

Run: python scripts/build_fixtures.py   then   python scripts/validate_contracts.py
Edit the story here, not the JSON files. The mock brain (MOCK=1) replays these.
"""
import json
import pathlib
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "contracts" / "fixtures"
T0 = datetime(2026, 11, 7, 20, 14, 0, tzinfo=timezone.utc)  # 2:14 pm Central


def ts(sec):
    return (T0 + timedelta(seconds=sec)).isoformat().replace("+00:00", "Z")


U = "usr_maya"
CALL = "call_t2"
CASE = "case_t2"
RUN = "run_t2"
SRC_EVENTS = {"name": "Account event log (synthetic)"}

user = {"user_id": U, "name": "Maya", "persona": "68, retired teacher. One laptop + one phone for 4 years, pays her bill monthly, never changed her SIM, uses the store for help.", "face_enabled": False}

call_started = {"event_id": "evt_t2_01", "user_id": U, "type": "call.started", "ts": ts(0), "source": "voice", "call_id": CALL,
                "data": {"direction": "in", "other_number_hash": "h_8f2c19", "caller_name": "T-Mobile Support", "attestation": "C", "seen_before": False, "scam_label": False}}
login = {"event_id": "evt_t2_02", "user_id": U, "type": "login", "ts": ts(940), "source": "portal", "call_id": CALL,
         "data": {"device_hash": "h_maya_laptop", "region": "Dallas, TX", "new_device": False, "succeeded": True}}
portal_signals = {"event_id": "evt_t2_03", "user_id": U, "type": "portal.signals", "ts": ts(1030), "source": "portal", "call_id": CALL,
                  "data": {"session_id": "ses_t2", "page_path": ["/portal", "/portal/security", "/portal/security/port-out"],
                           "ms_per_step": [6200, 41000, 9800], "hesitation_ms": 41000, "paste_into_pin": False, "tab_switches": 3,
                           "pointer_speed": 0.42, "typing_rhythm_distance": 1.1}}
protection_off = {"event_id": "evt_t2_04", "user_id": U, "type": "protection.changed", "ts": ts(1070), "source": "portal", "call_id": CALL,
                  "data": {"name": "port_out_protection", "enabled": False, "via": "portal"}}
transfer_pin = {"event_id": "evt_t2_05", "user_id": U, "type": "transfer_pin.requested", "ts": ts(1145), "source": "portal", "call_id": CALL, "data": {}}
timeline_events = [call_started, login, portal_signals, protection_off, transfer_pin]

call_summary = {"call_id": CALL, "caller_name": "T-Mobile Support", "attestation": "C", "seen_before": False, "scam_label": False,
                "started_at": ts(0), "ended_at": ts(1262), "duration_s": 1262}
active_call = dict(call_summary, ended_at=None, duration_s=1145)

risk = {"threat": "coached", "probability": 0.87, "calibrated": True, "confidence": "high", "anomaly": 0.34,
        "top_reasons": [
            {"feature": "protection_off_during_unverified_call", "contribution": 0.31, "text": "Port Out Protection was turned off during a call from an unverified number"},
            {"feature": "transfer_pin_during_call", "contribution": 0.22, "text": "Transfer PIN requested 19 minutes into that call"},
            {"feature": "first_transfer_pin_ever", "contribution": 0.12, "text": "Maya has never requested a transfer PIN before"},
            {"feature": "tab_switches", "contribution": 0.07, "text": "Left the page 3 times mid-flow"},
            {"feature": "known_device_home_region", "contribution": -0.05, "text": "Her own laptop, her usual region: it is really her"}],
        "model": "ml+rules"}

signals = [
    {"group": "call", "name": "active_call_minutes", "value": 19, "baseline": None, "note": "Unverified (STIR/SHAKEN C), never contacted her before", "source": {"name": "Call record (simulated carrier signal)", "record": f"calls/{CALL}"}},
    {"group": "call", "name": "caller_name_claims_tmobile", "value": True, "baseline": None, "source": {"name": "Caller ID name", "record": f"calls/{CALL}"}},
    {"group": "protection", "name": "port_out_protection_turned_off_s_ago", "value": 75, "baseline": None, "note": "During the call", "source": {"name": "Protection log", "record": "events/evt_t2_04"}},
    {"group": "account", "name": "transfer_pins_last_4y", "value": 0, "baseline": 0, "source": {"name": "Account history", "record": "events/evt_t2_05"}},
    {"group": "device", "name": "known_device", "value": True, "baseline": True, "source": {"name": "Device registry", "record": "events/evt_t2_02"}},
    {"group": "location", "name": "same_region_as_line", "value": True, "baseline": True, "source": {"name": "Login region vs line region", "record": "events/evt_t2_02"}},
    {"group": "portal", "name": "hesitation_s", "value": 41, "baseline": 6, "source": {"name": "Portal behavior (derived)", "record": "events/evt_t2_03"}},
    {"group": "portal", "name": "tab_switches", "value": 3, "baseline": 0, "source": {"name": "Portal behavior (derived)", "record": "events/evt_t2_03"}},
]

verification = {"status": "verified", "claims_checked": 7, "claims_dropped": 0, "notes": ["Every claim matched a tool result.", "Confidence kept at high."]}


def action(aid, kind, direction, status, req, desc, t_created, t_applied=None, via=None):
    return {"action_id": aid, "case_id": CASE, "kind": kind, "direction": direction, "status": status, "requires_approval": req,
            "approved_via": via, "description": desc, "created_at": ts(t_created), "applied_at": ts(t_applied) if t_applied else None}


actions = [
    action("act_t2_relock", "relock", "safer", "applied", False, "Turned Port Out Protection back on", 1150, 1150),
    action("act_t2_hold", "hold_transfer_pin", "safer", "applied", False, "Held the transfer PIN for 24 hours so it can't be used", 1150, 1150),
    action("act_t2_reset_pin", "reset_pin", "safer", "applied", True, "Reset your account PIN", 1240, 1250, "voice"),
    action("act_t2_revoke", "revoke_transfer_pin", "safer", "applied", True, "Cancel the pending transfer PIN", 1240, 1253, "voice"),
    action("act_t2_signout", "sign_out_sessions", "safer", "applied", True, "Sign out all other devices", 1240, 1256, "voice"),
    action("act_t2_report", "report_number", "safer", "applied", True, "Report the caller's number so other customers get warned", 1240, 1259, "voice"),
    action("act_t2_notify", "notify_trusted_contact", "safer", "rejected", True, "Let your daughter know", 1240, None, "voice"),
]

summary = {
    "case_number": "TTN-4821",
    "what_happened": "While you were on a 19-minute call with a number calling itself \"T-Mobile Support\", someone asked you to turn off Port Out Protection and create a transfer PIN.",
    "why_we_stepped_in": "That number couldn't be verified and had never contacted you before, and turning off protection during a call like this is a common scam pattern.",
    "confidence_text": "We're fairly confident this was a scam, but not certain.",
    "what_we_did": ["Turned Port Out Protection back on", "Held your transfer PIN for 24 hours so it can't be used"],
    "you_approved": ["Reset your account PIN", "Cancelled the pending transfer PIN", "Signed out other devices", "Reported the number"],
    "next_steps": ["Nothing else is needed. Your number is safe.", "If you shared bank details on that call, call your bank using the number on your card.", "Reply REPORT and we'll fill in an FTC report for you."],
    "spot_it_next_time": "T-Mobile will never call and ask you to turn off protection or read out a PIN or code.",
    "data_we_looked_at": ["When your call started and whether the number was verified", "Account changes made during that call", "Whether this was your usual device and area"],
    "replies": [{"keyword": "REPORT", "meaning": "Draft an FTC report"}, {"keyword": "UNDO", "meaning": "Safely release the hold (after the call, with a check)"}],
}

messages = [
    {"message_id": "msg_t2_heads_up", "case_id": CASE, "channel": "imessage", "direction": "out", "kind": "heads_up", "ts": ts(5),
     "text": "Titan: Heads up. The call you just answered says it's T-Mobile, but we can't verify it. We'll never ask for your PIN or ask you to turn off protection."},
    {"message_id": "msg_t2_alert", "case_id": CASE, "channel": "imessage", "direction": "out", "kind": "alert", "ts": ts(1152),
     "text": "Titan: Maya, you're on a call with a number we can't verify that says it's T-Mobile. We never ask you to turn off protection or share a transfer PIN on a call. Your number is safe and locked again. Was this your idea? Reply YES or NO."},
    {"message_id": "msg_t2_tr1", "case_id": CASE, "channel": "voice", "direction": "out", "kind": "transcript", "ts": ts(1214),
     "text": "Hi Maya, this is Titan, your account security. I'll never ask you for a PIN or a code. The person you're talking to isn't T-Mobile. Please hang up on them. I'll stay on the line."},
    {"message_id": "msg_t2_tr2", "case_id": CASE, "channel": "voice", "direction": "in", "kind": "transcript", "ts": ts(1236),
     "text": "He said my account was being hacked. I told him my PIN."},
    {"message_id": "msg_t2_summary", "case_id": CASE, "channel": "imessage", "direction": "out", "kind": "summary", "ts": ts(1270),
     "text": "Titan · Case TTN-4821. What happened: someone on an unverified call asked you to turn off Port Out Protection and create a transfer PIN. What we did: re-locked it and held the PIN. You approved: PIN reset, PIN cancelled, devices signed out, number reported. T-Mobile will never ask you to turn off protection or read out a PIN. Reply REPORT for an FTC report."},
]

STEPS = [
    (1145, "system", "trigger", "plan", "Transfer PIN requested during an unverified call", {"event_id": "evt_t2_05"}),
    (1146, "context", "context", "plan", "Checking her account, protections, the call and how she used the portal", {}),
    (1146, "context", "context", "tool_call", "call_context(usr_maya)", {"tool": "call_context"}),
    (1146, "context", "context", "tool_call", "protection_status(usr_maya)", {"tool": "protection_status"}),
    (1146, "context", "context", "tool_call", "account_history(usr_maya, 4y)", {"tool": "account_history"}),
    (1147, "context", "context", "tool_result", "On a call for 19 min · unverified (C) · never contacted her", {"tool": "call_context", "result": {"active": True, "minutes": 19, "attestation": "C", "seen_before": False}}),
    (1147, "context", "context", "tool_result", "Port Out Protection turned off 75 s ago, during the call", {"tool": "protection_status"}),
    (1147, "context", "context", "tool_result", "First transfer PIN in 4 years · her usual laptop · her usual area", {"tool": "account_history"}),
    (1148, "context", "context", "signal", "Portal: 41 s hesitation on Security, left the page 3 times", {"signals": ["hesitation_s", "tab_switches"]}),
    (1148, "risk", "risk", "tool_call", "ml.score(usr_maya, evt_t2_05)", {"tool": "ml.score"}),
    (1149, "risk", "risk", "score", "Coached victim · 87% (calibrated) · it's really her", {"risk": risk}),
    (1150, "verifier", "verify", "verify", "7 claims checked against the data · 0 dropped", {"verification": verification}),
    (1150, "response", "respond", "action", "Port Out Protection turned back on", {"action_id": "act_t2_relock"}),
    (1150, "response", "respond", "action", "Transfer PIN held for 24 hours", {"action_id": "act_t2_hold"}),
    (1152, "messaging", "reach", "message", "iMessage sent: \"Was this your idea? Reply YES or NO\"", {"message_id": "msg_t2_alert"}),
    (1153, "system", "await", "plan", "Waiting for Maya's reply (60 s)", {"timeout_s": 60}),
    (1213, "response", "reach", "call", "No reply in 60 s · Titan is calling Maya", {"purpose": "scam_intervention"}),
    (1214, "voice", "reach", "transcript", "Titan: \"The person you're talking to isn't T-Mobile. Please hang up. I'll stay on the line.\"", {"message_id": "msg_t2_tr1"}),
    (1236, "voice", "reach", "transcript", "Maya: \"He said my account was being hacked. I told him my PIN.\"", {"message_id": "msg_t2_tr2"}),
    (1240, "response", "recover", "approval_needed", "Recovery plan: reset PIN · cancel transfer PIN · sign out devices · report number · tell her daughter", {"action_ids": ["act_t2_reset_pin", "act_t2_revoke", "act_t2_signout", "act_t2_report", "act_t2_notify"]}),
    (1250, "voice", "recover", "approved", "Approved by voice: reset account PIN", {"action_id": "act_t2_reset_pin"}),
    (1253, "voice", "recover", "approved", "Approved by voice: cancel transfer PIN", {"action_id": "act_t2_revoke"}),
    (1256, "voice", "recover", "approved", "Approved by voice: sign out other devices", {"action_id": "act_t2_signout"}),
    (1259, "voice", "recover", "approved", "Approved by voice: report the number", {"action_id": "act_t2_report"}),
    (1265, "response", "summary", "summary", "Incident summary written and checked", {"summary": summary}),
    (1270, "messaging", "summary", "message", "Incident summary sent by iMessage (no links)", {"message_id": "msg_t2_summary"}),
    (1271, "system", "watch", "plan", "Watching her line for 24 hours for follow-up scams", {"until": ts(1271 + 86400)}),
    (1271, "system", "watch", "done", "Run complete", {}),
]
steps = [{"seq": i, "case_id": CASE, "run_id": RUN, "ts": ts(t), "agent": a, "stage": s, "type": ty, "title": title, "data": data}
         for i, (t, a, s, ty, title, data) in enumerate(STEPS)]

case_detail = {
    "case_id": CASE, "case_number": "TTN-4821", "user_id": U, "title": "Coached to turn off Port Out Protection during a fake support call",
    "status": "watching", "threat": "coached", "confidence": "high", "created_at": ts(1145), "updated_at": ts(1271),
    "user": user, "call": call_summary, "timeline": timeline_events, "risk": risk, "signals": signals, "verification": verification,
    "steps": steps, "actions": actions, "messages": messages, "summary": summary,
    "data_used": ["Call start time, duration, caller-ID name and verification (no audio, no content)",
                  "Protection changes and transfer PIN request during the call",
                  "Whether the device and area were her usual ones",
                  "Portal behavior as derived numbers (no keystrokes)"],
}

files = {
    "user.maya.json": user,
    "event.call_started.json": call_started,
    "event.login.json": login,
    "event.portal_signals.json": portal_signals,
    "event.protection_off.json": protection_off,
    "event.transfer_pin.json": transfer_pin,
    "event.t1_new_device_login.json": {"event_id": "evt_t1_01", "user_id": U, "type": "login", "ts": ts(-3600), "source": "portal", "call_id": None,
                                        "data": {"device_hash": "h_unknown_win11", "region": "Lagos, NG", "new_device": True, "succeeded": True}},
    "event.t1_sim_swap.json": {"event_id": "evt_t1_02", "user_id": U, "type": "sim_swap.requested", "ts": ts(-3500), "source": "portal", "call_id": None,
                               "data": {"new_device_hash": "h_unknown_esim", "channel": "portal"}},
    "event.t1b_otp_during_call.json": {"event_id": "evt_t1b_01", "user_id": U, "type": "otp.sent", "ts": ts(300), "source": "brain", "call_id": CALL, "data": {"purpose": "login"}},
    "event.t3_forwarded_text.json": {"event_id": "evt_t3_01", "user_id": U, "type": "message.forwarded", "ts": ts(-7200), "source": "messaging", "call_id": None,
                                     "data": {"channel": "imessage", "text": "T-Mobile: your account is locked. Verify now at t-mobile-secure-help.co to avoid suspension.", "from_hash": "h_31aa02"}},
    "event.customer_reply.json": {"event_id": "evt_t2_06", "user_id": U, "type": "customer.reply", "ts": ts(1240), "source": "voice", "call_id": None,
                                  "data": {"channel": "voice", "text": "I told him my PIN.", "case_id": CASE}},
    "event.face_result.json": {"event_id": "evt_face_01", "user_id": U, "type": "face.result", "ts": ts(1100), "source": "portal", "call_id": CALL,
                               "data": {"match": True, "similarity": 0.91, "liveness": 0.97, "antispoof": 0.95}},
    "checkreq.protection_off.json": {"user_id": U, "action": "protection_off", "protection": "port_out_protection", "portal_signals": portal_signals["data"]},
    "check.pause.json": {"check_id": "chk_t2_01", "decision": "pause", "reasons": ["Unverified call active for 18 min", "Caller ID claims to be T-Mobile", "Turning off a protection during that call"],
                         "during_call": True, "call": dict(active_call, duration_s=1065), "risk": None, "case_id": None, "hold_until": None,
                         "pause_screen": {"title": "Pause. Are you on the phone with someone who asked you to do this?",
                                          "body": "T-Mobile will never call and ask you to turn off protection or share a PIN. The call you're on right now is from a number we can't verify.",
                                          "help_label": "I'm on a call: help me", "continue_label": "I'm doing this on my own"}},
    "check.hold.json": {"check_id": "chk_t2_02", "decision": "hold", "reasons": ["Transfer PIN requested during an unverified call", "First transfer PIN in 4 years"],
                        "during_call": True, "call": active_call, "risk": risk, "case_id": CASE, "hold_until": ts(1145 + 86400), "pause_screen": None},
    "check.allow.json": {"check_id": "chk_ok_01", "decision": "allow", "reasons": ["No active call", "Usual device and area"], "during_call": False, "call": None,
                         "risk": None, "case_id": None, "hold_until": None, "pause_screen": None},
    "protections.maya.json": {"user_id": U, "protections": [
        {"name": "sim_protection", "enabled": True, "updated_at": ts(-86400 * 300)},
        {"name": "port_out_protection", "enabled": True, "updated_at": ts(1150)},
        {"name": "scam_block", "enabled": False, "updated_at": ts(-86400 * 300)}],
        "shield_mode": False, "transfer_pin": {"status": "revoked", "hold_until": None}},
    "risk.t2.json": risk,
    "risk.t1.json": {"threat": "takeover", "probability": 0.93, "calibrated": True, "confidence": "high", "anomaly": 0.88,
                     "top_reasons": [{"feature": "new_device", "contribution": 0.29, "text": "A device never seen on this account"},
                                     {"feature": "region_mismatch", "contribution": 0.27, "text": "Login from Lagos while her phone is in Dallas"},
                                     {"feature": "straight_to_sim_swap", "contribution": 0.18, "text": "Went straight to SIM swap after login"}],
                     "model": "ml+rules"},
    "risk.t3.json": {"threat": "scam_text", "probability": 0.96, "calibrated": True, "confidence": "high", "anomaly": None,
                     "top_reasons": [{"feature": "lookalike_domain", "contribution": 0.4, "text": "t-mobile-secure-help.co imitates T-Mobile"},
                                     {"feature": "domain_age_days", "contribution": 0.3, "text": "Domain registered 3 days ago"}],
                     "model": "ml+rules"},
    "send.alert.json": {"case_id": CASE, "user_id": U, "channel": "imessage", "kind": "alert", "text": messages[1]["text"], "expects_reply": True, "action_id": None},
    "callreq.t2.json": {"case_id": CASE, "user_id": U, "purpose": "scam_intervention",
                        "opening_line": "Hi Maya, this is Titan, your account security. I'll never ask you for a PIN or a code.",
                        "facts": ["She is on a 19-minute call with an unverified number claiming to be T-Mobile Support",
                                  "Port Out Protection was turned off during the call; Titan turned it back on",
                                  "The transfer PIN is on a 24-hour hold"],
                        "pending_action_ids": []},
    "summary.t2.json": summary,
    "caseevent.transcript.json": {"channel": "voice", "direction": "in", "kind": "transcript", "text": "He said my account was being hacked. I told him my PIN.", "agent": "voice"},
    "timeline.maya.json": {"user_id": U, "events": timeline_events, "calls": [call_summary], "active_call": None},
    "case.t2.json": case_detail,
    "scenario.t2.json": {"scenario_id": "scn_t2_0001", "user_id": U, "label": "coached", "hard_negative": False, "trigger_event_id": "evt_t2_05",
                         "events": timeline_events, "generator": {"seed": 42, "variant": "fake_support_port_out"}},
    "scenario.hard_negative_daughter.json": {"scenario_id": "scn_hn_0001", "user_id": U, "label": "legit", "hard_negative": True, "trigger_event_id": "evt_hn_03",
        "events": [
            {"event_id": "evt_hn_01", "user_id": U, "type": "call.started", "ts": ts(0), "source": "generator", "call_id": "call_hn",
             "data": {"direction": "out", "other_number_hash": "h_daughter", "caller_name": None, "attestation": "A", "seen_before": True, "scam_label": False}},
            {"event_id": "evt_hn_02", "user_id": U, "type": "login", "ts": ts(600), "source": "generator", "call_id": "call_hn",
             "data": {"device_hash": "h_maya_laptop", "region": "Dallas, TX", "new_device": False, "succeeded": True}},
            {"event_id": "evt_hn_03", "user_id": U, "type": "protection.changed", "ts": ts(700), "source": "generator", "call_id": "call_hn",
             "data": {"name": "scam_block", "enabled": True, "via": "portal"}}],
        "generator": {"seed": 42, "variant": "long_call_with_daughter_turns_protection_on"}},
}

for old in OUT.iterdir():
    old.unlink()
for name, obj in files.items():
    (OUT / name).write_text(json.dumps(obj, indent=2) + "\n")
with open(OUT / "stream.t2.sse", "w") as f:
    for s in steps:
        f.write(f"event: step\ndata: {json.dumps(s)}\n\n")
print(f"wrote {len(files) + 1} fixture files ({len(steps)} stream steps)")
