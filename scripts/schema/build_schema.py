"""Builds contracts/schema.json (v0.3, Titan). Edit here, then run: python scripts/schema/build_schema.py contracts/schema.json"""
import json, sys

S = lambda **k: {"type": "string", **k}
N = lambda **k: {"type": "number", **k}
I = lambda **k: {"type": "integer", **k}
B = {"type": "boolean"}
TS = S(format="date-time")
def R(name): return {"$ref": f"#/$defs/{name}"}
def A(item, **k): return {"type": "array", "items": item, **k}
def O(props, req=None, extra=False, desc=None):
    o = {"type": "object", "properties": props, "required": req if req is not None else list(props), "additionalProperties": extra}
    if desc: o["description"] = desc
    return o
def nullable(x): return {"anyOf": [x, {"type": "null"}]}
def E(*vals): return {"type": "string", "enum": list(vals)}

PROTECTIONS = E("sim_protection", "port_out_protection", "scam_block")
ATTEST = E("A", "B", "C", "none")
EVENT_TYPES = ["call.started", "call.ended", "login", "otp.sent", "otp.entered", "pin.attempt",
               "protection.changed", "transfer_pin.requested", "sim_swap.requested", "portal.signals",
               "message.forwarded", "customer.reply", "face.result"]
ACTION_KINDS = E("relock", "hold_transfer_pin", "require_step_up", "reset_pin", "revoke_transfer_pin",
                 "sign_out_sessions", "report_number", "notify_trusted_contact", "send_ftc_report", "release_hold")
SENSITIVE = E("protection_off", "transfer_pin", "sim_swap", "change_email", "change_password", "add_line", "login")

d = {}
d["Source"] = O({"name": S(), "url": S(), "record": S(description="Internal record ref, e.g. events/evt_123")}, ["name"],
                desc="Where a fact came from. Every Signal and claim carries one.")
d["Error"] = O({"error": S(), "detail": S()}, ["error"])
d["User"] = O({"user_id": S(pattern="^usr_"), "name": S(), "persona": S(), "face_enabled": B}, ["user_id", "name", "face_enabled"])

d["CallData"] = O({"direction": E("in", "out"), "other_number_hash": S(), "caller_name": nullable(S()),
                   "attestation": ATTEST, "seen_before": B, "scam_label": B},
                  ["direction", "other_number_hash", "attestation", "seen_before", "scam_label"],
                  desc="call.started payload. Metadata only, never content. Simulated carrier signal in the demo.")
d["CallEndedData"] = O({"duration_s": I(minimum=0)})
d["LoginData"] = O({"device_hash": S(), "region": S(), "new_device": B, "succeeded": B})
d["OtpData"] = O({"purpose": E("login", "account_change", "transfer_pin")})
d["PinAttemptData"] = O({"ok": B, "channel": E("portal", "app", "care")})
d["ProtectionChangeData"] = O({"name": PROTECTIONS, "enabled": B, "via": E("portal", "app", "care", "titan")})
d["SimSwapData"] = O({"new_device_hash": S(), "channel": E("portal", "app", "care", "store")})
d["PortalSignals"] = O({
    "session_id": S(), "page_path": A(S()), "ms_per_step": A(N(minimum=0)),
    "hesitation_ms": N(minimum=0), "paste_into_pin": B, "tab_switches": I(minimum=0),
    "pointer_speed": nullable(N(minimum=0)), "typing_rhythm_distance": nullable(N(minimum=0)),
}, ["session_id", "page_path", "hesitation_ms", "paste_into_pin", "tab_switches"],
   desc="Derived numbers only. Never keystrokes or typed text.")
d["ForwardedMessage"] = O({"channel": E("imessage", "sms"), "text": S(maxLength=4096), "image_url": S(), "from_hash": S()},
                          ["channel"])
d["CustomerReply"] = O({"channel": E("imessage", "sms", "voice", "web"), "text": S(maxLength=4096), "case_id": S()},
                       ["channel", "text"])
d["FaceResult"] = O({"match": B, "similarity": N(minimum=0, maximum=1), "liveness": N(minimum=0, maximum=1),
                     "antispoof": N(minimum=0, maximum=1)}, desc="Computed on the device. No images or descriptors leave it.")

data_for = {"call.started": "CallData", "call.ended": "CallEndedData", "login": "LoginData", "otp.sent": "OtpData",
            "otp.entered": "OtpData", "pin.attempt": "PinAttemptData", "protection.changed": "ProtectionChangeData",
            "sim_swap.requested": "SimSwapData", "portal.signals": "PortalSignals",
            "message.forwarded": "ForwardedMessage", "customer.reply": "CustomerReply", "face.result": "FaceResult"}
d["Event"] = {
    "type": "object",
    "description": "Anything that happened on the account. POST /events. Idempotent on event_id.",
    "properties": {"event_id": S(pattern="^evt_"), "user_id": S(pattern="^usr_"), "type": E(*EVENT_TYPES), "ts": TS,
                   "source": E("portal", "voice", "messaging", "console", "watcher", "generator", "brain"),
                   "call_id": nullable(S(pattern="^call_")), "data": {"type": "object"}},
    "required": ["event_id", "user_id", "type", "ts", "source", "data"],
    "additionalProperties": False,
    "allOf": [{"if": {"properties": {"type": {"const": t}}}, "then": {"properties": {"data": R(n)}}} for t, n in data_for.items()],
}
d["CallSummary"] = O({"call_id": S(pattern="^call_"), "caller_name": nullable(S()), "attestation": ATTEST,
                      "seen_before": B, "scam_label": B, "started_at": TS, "ended_at": nullable(TS),
                      "duration_s": I(minimum=0)})
d["Timeline"] = O({"user_id": S(), "events": A(R("Event")), "calls": A(R("CallSummary")), "active_call": nullable(R("CallSummary"))})

d["ProtectionState"] = O({
    "user_id": S(),
    "protections": A(O({"name": PROTECTIONS, "enabled": B, "updated_at": TS})),
    "shield_mode": {"type": "boolean", "description": "True while an unverified call is active: turning protections off needs the pause screen (+ face check if enabled)."},
    "transfer_pin": O({"status": E("none", "held", "active", "revoked"), "hold_until": nullable(TS)}),
})
d["ProtectionChangeRequest"] = O({"enabled": B, "via": E("portal", "titan", "care"), "check_id": S(description="From POST /check; required when turning a protection off")},
                                 ["enabled", "via"])
d["CheckRequest"] = O({"user_id": S(pattern="^usr_"), "action": SENSITIVE, "protection": PROTECTIONS,
                       "portal_signals": R("PortalSignals"), "face": R("FaceResult"),
                       "customer_choice": E("on_call_help", "doing_it_myself")},
                      ["user_id", "action"], desc="Fast gate before a sensitive action. No LLM. Must answer in < 300 ms.")
d["CheckResponse"] = O({"check_id": S(pattern="^chk_"), "decision": E("allow", "pause", "hold", "block"),
                        "reasons": A(S()), "during_call": B, "call": nullable(R("CallSummary")),
                        "risk": nullable(R("RiskScore")), "case_id": nullable(S()), "hold_until": nullable(TS),
                        "pause_screen": nullable(O({"title": S(), "body": S(), "help_label": S(), "continue_label": S()}))},
                       ["check_id", "decision", "reasons", "during_call"])

d["Signal"] = O({"group": E("account", "device", "protection", "call", "location", "portal", "face", "message"),
                 "name": S(), "value": {"type": ["number", "string", "boolean", "null"]},
                 "baseline": {"type": ["number", "string", "boolean", "null"]}, "note": S(), "source": R("Source")},
                ["group", "name", "value", "source"])
d["RiskScore"] = O({"threat": E("takeover", "coached", "scam_text", "bot", "legit"),
                    "probability": N(minimum=0, maximum=1), "calibrated": B,
                    "confidence": E("low", "medium", "high"), "anomaly": nullable(N(minimum=0, maximum=1)),
                    "top_reasons": A(O({"feature": S(), "contribution": N(), "text": S()})),
                    "model": E("rules", "ml", "ml+rules")},
                   ["threat", "probability", "calibrated", "confidence", "top_reasons", "model"],
                   desc="Output of ml.score() (Lane 2b) and of the Risk agent.")
d["Verification"] = O({"status": E("verified", "downgraded"), "claims_checked": I(minimum=0),
                       "claims_dropped": I(minimum=0), "notes": A(S())})
d["Action"] = O({"action_id": S(pattern="^act_"), "case_id": S(), "kind": ACTION_KINDS, "direction": E("safer", "looser"),
                 "status": E("proposed", "awaiting_approval", "approved", "rejected", "applied", "failed"),
                 "requires_approval": B, "approved_via": nullable(E("web", "sms", "voice")), "description": S(),
                 "created_at": TS, "applied_at": nullable(TS)},
                ["action_id", "case_id", "kind", "direction", "status", "requires_approval", "description", "created_at"],
                desc="Safer actions may apply automatically. Looser ones always need approval and no active suspicious call.")
d["Message"] = O({"message_id": S(pattern="^msg_"), "case_id": S(), "channel": E("imessage", "sms", "voice"),
                  "direction": E("in", "out"), "kind": E("heads_up", "alert", "question", "summary", "recovery_step", "info", "reply", "transcript"),
                  "text": S(), "ts": TS}, ["message_id", "case_id", "channel", "direction", "kind", "text", "ts"])
d["IncidentSummary"] = O({"case_number": S(), "what_happened": S(), "why_we_stepped_in": S(), "confidence_text": S(),
                          "what_we_did": A(S()), "you_approved": A(S()), "next_steps": A(S()),
                          "spot_it_next_time": S(), "data_we_looked_at": A(S()), "replies": A(O({"keyword": S(), "meaning": S()}))},
                         desc="Sent as one iMessage with no links. Every sentence checked by the Verifier.")
d["StepEvent"] = O({"seq": I(minimum=0), "case_id": S(), "run_id": S(pattern="^run_"), "ts": TS,
                    "agent": E("system", "context", "risk", "verifier", "response", "messaging", "voice"),
                    "stage": E("trigger", "context", "risk", "verify", "respond", "reach", "await", "recover", "summary", "watch"),
                    "type": E("plan", "tool_call", "tool_result", "signal", "score", "verify", "action", "message",
                              "call", "transcript", "approval_needed", "approved", "summary", "error", "done"),
                    "title": S(), "data": {"type": "object"}},
                   ["seq", "case_id", "run_id", "ts", "agent", "stage", "type", "title", "data"],
                   desc="One line on the dashboard. Streamed on GET /cases/{id}/stream as `event: step`.")
d["Case"] = O({"case_id": S(pattern="^case_"), "case_number": S(), "user_id": S(), "title": S(),
               "status": E("open", "awaiting_reply", "recovering", "watching", "closed"),
               "threat": nullable(E("takeover", "coached", "scam_text", "bot", "legit")),
               "confidence": nullable(E("low", "medium", "high")), "created_at": TS, "updated_at": TS})
case_detail_props = dict(d["Case"]["properties"])
case_detail_props.update({"user": R("User"), "call": nullable(R("CallSummary")), "timeline": A(R("Event")),
                          "risk": nullable(R("RiskScore")), "signals": A(R("Signal")), "verification": nullable(R("Verification")),
                          "steps": A(R("StepEvent")), "actions": A(R("Action")), "messages": A(R("Message")),
                          "summary": nullable(R("IncidentSummary")), "data_used": A(S())})
d["CaseDetail"] = O(case_detail_props, desc="GET /cases/{id}. Everything the dashboard and the customer /case page need.")
d["CaseEventRequest"] = O({"channel": E("imessage", "sms", "voice", "web"), "direction": E("in", "out"), "kind": E("transcript", "reply", "info", "delivery"), "text": S(maxLength=4096), "agent": E("voice", "messaging", "system")}, ["channel", "direction", "kind", "text"], desc="Doors -> brain POST /cases/{id}/events (transcript lines, replies, delivery receipts).")
d["ApprovalRequest"] = O({"via": E("web", "sms", "voice"), "note": S()}, ["via"])
d["SendRequest"] = O({"case_id": S(), "user_id": S(), "channel": E("imessage", "sms"),
                      "kind": E("heads_up", "alert", "question", "summary", "recovery_step", "info"),
                      "text": S(maxLength=2000), "expects_reply": B, "action_id": nullable(S())},
                     ["case_id", "user_id", "channel", "kind", "text", "expects_reply"],
                     desc="Brain -> messaging POST /internal/send. Messaging resolves the phone number; text never has links.")
d["CallRequest"] = O({"case_id": S(), "user_id": S(), "purpose": E("scam_intervention", "verify_it_was_you"),
                      "opening_line": S(), "facts": A(S()), "pending_action_ids": A(S())},
                     desc="Brain -> voice POST /internal/call.")
d["DatasetScenario"] = O({"scenario_id": S(), "user_id": S(), "label": E("takeover", "coached", "scam_text", "bot", "recovery_scam", "legit"),
                          "hard_negative": B, "trigger_event_id": S(), "events": A(R("Event")),
                          "generator": O({"seed": I(), "variant": S()})},
                         desc="One labeled scenario. Lane 2a writes these; Lane 2b trains and evaluates on them.")

schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "titan/contracts/v0.3",
          "title": "Titan contracts v0.3", "$defs": d}
json.dump(schema, open(sys.argv[1], "w"), indent=2)
print("defs:", len(d))
