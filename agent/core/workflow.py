"""The real workflow (MOCK=0): Context -> Risk -> Verifier -> Response -> reach -> await -> recover -> summary -> watch.

Every step is streamed as a StepEvent. Model calls run in threads so the event loop (and SSE) stays live.
If a model call fails, the step is marked `error` and a deterministic fallback keeps the run going.
Timers: REPLY_TIMEOUT_S (60) before Titan calls; RECOVERY_TIMEOUT_S (240) to collect approvals.
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import timedelta

from core import agents, outbound, toolbox
from core.store import Store, iso, new_id, now

_wakes: dict[str, asyncio.Event] = {}
_inbox: dict[str, list[dict]] = {}

REQUIRED_TOOLS = {
    "coached": ["call_context", "protection_status", "account_history", "device_sim_status", "location_match", "portal_signals"],
    "takeover": ["device_sim_status", "location_match", "account_history", "protection_status", "call_context"],
    "scam_text": ["check_message", "recent_scam_reports", "policy_lookup"],
}
DATA_USED = {
    "call_context": "Call start time, duration, caller-ID name and verification (no audio, no content)",
    "protection_status": "Protection changes and transfer PIN requests",
    "account_history": "Account history: past requests and known devices",
    "device_sim_status": "Device and SIM status",
    "location_match": "Whether the request came from her usual area (no location history)",
    "portal_signals": "Portal behavior as derived numbers (no keystrokes)",
    "check_message": "The text she forwarded",
    "recent_scam_reports": "Numbers and domains already reported",
    "policy_lookup": "Carrier security policy",
}


POLICY_Q = {
    "coached": "Does T-Mobile ever ask customers on a call to turn off Port Out Protection or share a transfer PIN?",
    "takeover": "What should happen when a SIM swap is requested from a new device in another region?",
    "scam_text": "Does T-Mobile send texts asking customers to verify their account through a link?",
}
_HOST = re.compile(r"\b([a-z0-9-]+(?:\.[a-z0-9-]+)*)\.(com|net|org|co|io|info|xyz|us|app|biz|site|online)\b", re.I)


def defang(text: str) -> str:
    """Write domains so they can't be tapped: t-mobile-secure-help[.]co (D-012: never send a link)."""
    text = re.sub(r"(?i)https?://", "", text or "")
    return _HOST.sub(lambda m: m.group(0).replace(".", "[.]"), text)


def notify(case_id: str, item: dict | None = None):
    """Doors call this (via the server) when a reply, transcript or approval arrives for a case."""
    if item is not None:
        _inbox.setdefault(case_id, []).append(item)
    ev = _wakes.get(case_id)
    if ev:
        ev.set()


async def _wait(case_id: str, timeout: float) -> list[dict]:
    ev = _wakes.setdefault(case_id, asyncio.Event())
    if not _inbox.get(case_id):
        try:
            await asyncio.wait_for(ev.wait(), timeout)
        except asyncio.TimeoutError:
            pass
    ev.clear()
    items, _inbox[case_id] = _inbox.get(case_id, []), []
    return items


def _t(name: str, default: float) -> float:
    return float(os.getenv(name, default))


class Run:
    def __init__(self, store: Store, case: dict, threat: str, trigger: dict):
        self.store, self.case, self.threat, self.trigger = store, case, threat, trigger
        self.uid = case["user_id"]
        self.run_id = new_id("run")
        self.results: dict[str, dict] = {}

    def step(self, agent, stage, type_, title, data=None):
        return self.store.add_step(self.case, self.run_id, agent, stage, type_, title, data or {})

    async def call(self, fn, *args):
        return await asyncio.to_thread(fn, *args)

    def action(self, kind: str, desc: str, *, applied: bool, approval: bool) -> dict:
        a = {"action_id": new_id("act"), "case_id": self.case["case_id"], "kind": kind,
             "direction": "looser" if kind == "release_hold" else "safer",
             "status": "applied" if applied else "awaiting_approval", "requires_approval": approval,
             "approved_via": None, "description": desc, "created_at": iso(now()), "applied_at": iso(now()) if applied else None}
        self.case["actions"].append(a)
        return a

    def story(self) -> str:
        """What happened, built only from tool results (never model wording), so the customer is told verified facts."""
        r = {k: (v.get("result") or {}) for k, v in self.results.items()}
        cc, ps, lm = r.get("call_context", {}), r.get("protection_status", {}), r.get("location_match", {})
        if self.case.get("threat") == "scam_text" or self.threat == "scam_text":
            cm = r.get("check_message", {})
            dom = (cm.get("lookalike_domains") or cm.get("domains") or ["an unknown site"])[0]
            age = re.search(r"registered (\d+) days? ago", self.results.get("check_message", {}).get("summary", ""))
            return defang(f"You forwarded a text that points to {dom}, which imitates T-Mobile's website"
                          + (f" and was registered {age.group(1)} days ago." if age else "."))
        if self.case.get("threat") == "takeover":
            where = f" in {lm.get('request_region')}" if lm.get("request_region") else ""
            phone = f" while your phone was in {lm.get('line_region')}" if lm.get("line_region") else ""
            return f"Someone signed in to your account from a new device{where}{phone} and asked to move your number to a new SIM."
        off = [n.replace("_", " ").title() for n in (ps.get("off_during_call") or [])]
        did = (" turn off " + " and ".join(off)) if off else ""
        pin = " request a transfer PIN" if self.trigger["type"] == "transfer_pin.requested" else ""
        asks = " and".join(x for x in (did, pin) if x) or " change your account security"
        caller = f" calling itself \"{cc['caller_name']}\"" if cc.get("caller_name") else ""
        mins = f"{cc['minutes']}-minute " if cc.get("minutes") else ""
        return f"While you were on a {mins}call with a number{caller} that we couldn't verify, someone asked you to{asks}."

    def send(self, kind: str, text: str, expects_reply: bool, action_id: str | None = None) -> dict:
        text = defang(text)
        ok, why = agents.outbound_ok(text)
        if not ok:
            self.step("verifier", "reach", "error", f"Blocked an outbound message ({why}); using the safe template", {"reason": why})
            text = TEMPLATES.get(kind, TEMPLATES["info"]).format(name=self.store.users[self.uid]["name"])
        msg = {"message_id": new_id("msg"), "case_id": self.case["case_id"], "channel": "imessage", "direction": "out",
               "kind": kind, "text": text, "ts": iso(now())}
        self.case["messages"].append(msg)
        outbound.send_message(self.store, {"case_id": self.case["case_id"], "user_id": self.uid, "channel": "imessage",
                                           "kind": kind, "text": text, "expects_reply": expects_reply, "action_id": action_id})
        return msg

    # ------------------------------------------------------------------ stages
    async def context(self):
        catalog = [{"name": n, "description": (f.__doc__ or n).strip().split("\n")[0]} for n, f in toolbox.tools().items()]
        required = REQUIRED_TOOLS.get(self.threat, REQUIRED_TOOLS["coached"])
        try:
            plan, model = await self.call(agents.context_plan, self.trigger, catalog)
            chosen = [t for t in plan.get("tools", []) if t in toolbox.tools()]
            self.step("context", "context", "plan", plan.get("plan") or "Planning what to check", {"model": model, "tools": chosen})
        except Exception as e:  # noqa: BLE001
            chosen = []
            self.step("context", "context", "error", f"Planner unavailable ({type(e).__name__}); using the standard checks", {})
        if self.threat != "scam_text":  # message checks only make sense for a forwarded text
            chosen = [t for t in chosen if t not in ("check_message",)]
        names = list(dict.fromkeys(required + chosen))
        def args_for(n):
            if n == "check_message":
                return {"text": self.trigger["data"].get("text", "")}
            if n == "policy_lookup":
                return {"question": POLICY_Q.get(self.threat, POLICY_Q["coached"])}
            return {"user_id": self.uid}
        args = {n: args_for(n) for n in names}
        for n in names:
            label = "forwarded text" if n == "check_message" else "policy question" if n == "policy_lookup" else self.uid
            self.step("context", "context", "tool_call", f"{n}({label})", {"tool": n})
        outs = await asyncio.gather(*(asyncio.to_thread(toolbox.run_tool, self.store, n, args[n]) for n in names))
        for n, out in zip(names, outs):
            self.results[n] = out
            self.step("context", "context", "tool_result", out["summary"], {"tool": n, "result": out.get("result"), "source": out.get("source")})
        self.case["data_used"] = [DATA_USED[n] for n in names if n in DATA_USED]
        try:
            f, model = await self.call(agents.context_facts, self.trigger, self.results)
            self.facts = [x for x in f.get("facts", []) if x.get("tool") in self.results]
        except Exception:  # noqa: BLE001
            self.facts = []
        if not self.facts:
            self.facts = [{"fact": r["summary"], "tool": n} for n, r in self.results.items()]
        self.case["signals"] = [{"group": "call" if n == "call_context" else "account", "name": n, "value": r["summary"],
                                 "baseline": None, "source": r.get("source") or {"name": n}} for n, r in self.results.items()]
        self.step("context", "context", "signal", f"{len(self.facts)} facts gathered", {"facts": self.facts})

    async def risk(self):
        self.step("risk", "risk", "tool_call", f"ml.score({self.uid}, {self.trigger['type']})", {"tool": "ml.score"})
        score = await self.call(toolbox.score, self.store, self.uid, self.trigger)
        self.score = score
        floor = "hold_and_alert" if score["threat"] in ("coached", "takeover") and score["probability"] >= 0.5 else "allow"
        try:
            r, model = await self.call(agents.risk, self.trigger, self.facts, score)
        except Exception as e:  # noqa: BLE001
            r, model = {}, None
            self.step("risk", "risk", "error", f"Risk reasoning unavailable ({type(e).__name__}); using the model score", {})
        order = ["allow", "step_up_face", "hold_and_alert", "block"]
        decision = r.get("decision") if r.get("decision") in order else floor
        decision = max(decision, floor, key=order.index)  # the model can't go below the rules floor
        threat = score["threat"] if score["threat"] != "legit" else (r.get("threat") or "legit")
        self.claims = [c for c in r.get("claims", []) if isinstance(c, dict) and c.get("claim")] or \
            [{"claim": x["text"], "tool": "ml.score"} for x in score["top_reasons"][:3]]
        self.assessment = r.get("assessment") or "; ".join(x["text"] for x in score["top_reasons"][:3])
        self.decision = decision
        self.case.update(threat=threat, confidence=score["confidence"], risk=score)
        label = {"coached": "Coached victim", "takeover": "Account takeover", "scam_text": "Scam text", "bot": "Bot", "legit": "Looks legitimate"}[threat]
        self.step("risk", "risk", "score", f"{label} · {round(score['probability'] * 100)}% ({'calibrated' if score['calibrated'] else score['model']}) · {decision.replace('_', ' ')}",
                  {"risk": score, "decision": decision, "assessment": self.assessment, "model": model})

    async def verify(self):
        checkable = [c for c in self.claims if c.get("tool") in self.results or c.get("tool") == "ml.score"]
        dropped = len(self.claims) - len(checkable)
        notes = []
        try:
            raw = dict(self.results) | {"ml.score": {"result": self.score}}
            v, model = await self.call(agents.verify, checkable, raw)
            verdicts = {x.get("index"): x for x in v.get("results", [])}
            kept = []
            for i, c in enumerate(checkable):
                if verdicts.get(i, {}).get("supported", True):
                    kept.append(c)
                else:
                    dropped += 1
                    notes.append(f"Dropped: {c['claim']} ({verdicts[i].get('note', 'not in the data')})")
        except Exception as e:  # noqa: BLE001
            kept = checkable
            notes.append(f"Verifier unavailable ({type(e).__name__}); only tool-linked claims kept")
        self.claims = kept
        status = "verified" if dropped == 0 else "downgraded"
        if dropped and self.case["confidence"] == "high":
            self.case["confidence"] = "medium"
        self.case["verification"] = {"status": status, "claims_checked": len(kept) + dropped, "claims_dropped": dropped,
                                     "notes": notes or ["Every claim matched a tool result."]}
        self.step("verifier", "verify", "verify", f"{len(kept) + dropped} claims checked against the data · {dropped} dropped",
                  {"verification": self.case["verification"], "claims": kept})

    async def respond(self) -> bool:
        """Safer-only actions through the protections, then the alert. Returns True if we should wait for her."""
        st, taken = self.store, []
        if self.threat == "scam_text" or self.case["threat"] == "scam_text":
            text = (f"Titan: This text is a scam. {self.story()} "
                    "Don't tap anything in it. T-Mobile will never ask you to verify your account by text.")
            self.send("info", text, False)
            self.step("messaging", "reach", "message", "Reply sent: this text is a scam", {})
            return False
        if self.decision in ("hold_and_alert", "block"):
            for name in self.results.get("protection_status", {}).get("result", {}).get("off_during_call", []) or []:
                st.set_protection(self.uid, name, True)
                a = self.action("relock", f"Turned {name.replace('_', ' ').title()} back on", applied=True, approval=False)
                taken.append(a["description"])
                self.step("response", "respond", "action", a["description"], {"action_id": a["action_id"]})
            if st.transfer_pins[self.uid]["status"] in ("active", "held") or self.trigger["type"] == "transfer_pin.requested":
                st.hold_transfer_pin(self.uid)
                a = self.action("hold_transfer_pin", "Held the transfer PIN for 24 hours so it can't be used", applied=True, approval=False)
                taken.append(a["description"])
                self.step("response", "respond", "action", a["description"], {"action_id": a["action_id"]})
            if self.case["threat"] == "takeover":
                st.set_protection(self.uid, "sim_protection", True)
                a = self.action("relock", "Blocked the SIM swap and locked SIM Protection", applied=True, approval=False)
                taken.append(a["description"])
                self.step("response", "respond", "action", a["description"], {"action_id": a["action_id"]})
        self.taken = taken
        on_call = bool(st.active_call(self.uid))
        name = st.users[self.uid]["name"]
        try:
            words, model = await self.call(agents.response_text, name, self.case["threat"], self.story(),
                                           [c["claim"] for c in self.claims], taken, on_call)
        except Exception:  # noqa: BLE001
            words = {}
        self.call_words = words
        alert = words.get("alert_text") or TEMPLATES["alert"].format(name=name)
        self.send("alert", alert, True)
        self.step("messaging", "reach", "message", f"iMessage sent: \"{alert[:90]}{'…' if len(alert) > 90 else ''}\"", {})
        return True

    async def reach_and_wait(self):
        self.case["status"] = "awaiting_reply"
        timeout = _t("REPLY_TIMEOUT_S", 60)
        self.step("system", "await", "plan", f"Waiting for {self.store.users[self.uid]['name']}'s reply ({int(timeout)} s)", {"timeout_s": timeout})
        items = await _wait(self.case["case_id"], timeout)
        reply = next((i for i in items if i.get("direction") == "in"), None)
        intent = await self.call(agents.read_reply, reply["text"], "Was this your idea?") if reply else None
        if intent and intent["intent"] == "yes":
            if self.store.suspicious(self.store.active_call(self.uid)):
                self.send("question", "Titan: Thanks. Please hang up that call first. Once you're off it, reply YES again and we'll release the hold safely.", True)
                self.step("response", "await", "plan", "She said it was her, but the suspicious call is still active: hold stays", {"intent": intent})
                return "hold"
            self.step("response", "await", "plan", "She confirmed it was her and she's off the call: no call needed", {"intent": intent})
            return "released"
        why = "No reply" if not reply else f"She replied: {intent['intent']}"
        self.step("response", "reach", "call", f"{why} · Titan is calling {self.store.users[self.uid]['name']}", {"purpose": "scam_intervention"})
        w = getattr(self, "call_words", {}) or {}
        outbound.place_call(self.store, {
            "case_id": self.case["case_id"], "user_id": self.uid, "purpose": "scam_intervention",
            "opening_line": w.get("call_opening_line") or "Hi, this is Titan, your account security. I'll never ask you for a PIN or a code.",
            "facts": (w.get("call_facts") or [c["claim"] for c in self.claims])[:4] + getattr(self, "taken", []),
            "pending_action_ids": []})
        return "called"

    async def recover(self):
        self.case["status"] = "recovering"
        plan = [("reset_pin", "Reset your account PIN"), ("sign_out_sessions", "Sign out all other devices")]
        if self.results.get("call_context", {}).get("result", {}).get("active"):
            plan.append(("report_number", "Report the caller's number so other customers get warned"))
        if any(a["kind"] == "hold_transfer_pin" for a in self.case["actions"]):
            plan.insert(1, ("revoke_transfer_pin", "Cancel the pending transfer PIN"))
        pending = [self.action(k, d, applied=False, approval=True) for k, d in plan]
        self.step("response", "recover", "approval_needed", "Recovery plan: " + " · ".join(a["description"] for a in pending),
                  {"action_ids": [a["action_id"] for a in pending]})
        prompted: set[str] = set()

        def prompt_next():
            """Text the next unanswered step (one question at a time, D-039 / D-042). Answers may come by text or on the call."""
            nxt = next((a for a in pending if a["status"] == "awaiting_approval"), None)
            if nxt and nxt["action_id"] not in prompted:
                prompted.add(nxt["action_id"])
                n = pending.index(nxt) + 1
                self.send("recovery_step", f"Titan: Step {n} of {len(pending)}. {nxt['description']}? Reply YES or NO.", True, nxt["action_id"])
                self.step("messaging", "recover", "message", f"Recovery question {n}/{len(pending)} sent: {nxt['description']}",
                          {"action_id": nxt["action_id"]})

        prompt_next()
        deadline = asyncio.get_running_loop().time() + _t("RECOVERY_TIMEOUT_S", 240)
        while any(a["status"] == "awaiting_approval" for a in pending):
            left = deadline - asyncio.get_running_loop().time()
            if left <= 0:
                break
            for item in await _wait(self.case["case_id"], left):
                if item.get("direction") == "in" and item.get("text"):  # free-form answer on the call or by text
                    intent = await self.call(agents.read_reply, item["text"], "recovery")
                    nxt = next((a for a in pending if a["status"] == "awaiting_approval"), None)
                    if nxt and intent["intent"] in ("yes", "no"):
                        apply_decision(self.store, self.case, nxt, intent["intent"] == "yes", item.get("channel", "sms"))
            prompt_next()  # also covers approvals that arrived on the call or the web
        for a in pending:
            if a["status"] == "awaiting_approval":
                a["status"] = "rejected"
                self.step("system", "recover", "action", f"No answer: {a['description']} (not done)", {"action_id": a["action_id"], "approved": False})

    async def summarize(self):
        st, name = self.store, self.store.users[self.uid]["name"]
        approved = [a["description"] for a in self.case["actions"] if a["requires_approval"] and a["status"] == "applied"]
        declined = [a["description"] for a in self.case["actions"] if a["requires_approval"] and a["status"] == "rejected"]
        said = [m["text"] for m in self.case["messages"] if m["direction"] == "in"][-3:]
        payload = {"customer_name": name, "case_number": self.case["case_number"], "threat": self.case["threat"],
                   "what_happened": self.story(), "facts": [c["claim"] for c in self.claims], "actions_taken": getattr(self, "taken", []),
                   "customer_approved": approved, "customer_declined": declined, "customer_said": said}
        try:
            s, model = await self.call(agents.summary_text, payload)
        except Exception:  # noqa: BLE001
            s = {}
        summary = {
            "case_number": self.case["case_number"],
            "what_happened": self.story(),
            "why_we_stepped_in": s.get("why_we_stepped_in") or self.assessment,
            "confidence_text": s.get("confidence_text") or {"high": "We're fairly confident this was a scam, but not certain.",
                                                           "medium": "This looked like a scam, but we're not sure.",
                                                           "low": "We weren't sure, so we checked with you."}[self.case["confidence"] or "medium"],
            "what_we_did": getattr(self, "taken", []) or ["Checked your account and let you know"],
            "you_approved": approved,
            "next_steps": (s.get("next_steps") or ["Nothing else is needed. Your number is safe."])[:3],
            "spot_it_next_time": s.get("spot_it_next_time") or "T-Mobile will never call and ask you to turn off protection or read out a PIN or code.",
            "data_we_looked_at": self.case["data_used"],
            "replies": [{"keyword": "REPORT", "meaning": "Draft an FTC report"},
                        {"keyword": "UNDO", "meaning": "Safely release the hold (after the call, with a check)"}],
        }
        replaced = {}
        for k in ("what_happened", "why_we_stepped_in", "spot_it_next_time", "confidence_text"):
            summary[k] = defang(summary[k])
            ok, why = agents.outbound_ok(summary[k], use_model=False)
            if not ok:
                replaced[k] = why
                summary[k] = "Titan stepped in to keep your number safe."
            summary[k] = _sentence(summary[k])
        summary["next_steps"] = [_sentence(x) for x in summary["next_steps"]]
        self.case["summary"] = summary
        self.step("response", "summary", "summary", "Incident summary written and checked", {"summary": summary, "replaced": replaced})
        text = (f"Titan · Case {summary['case_number']}. What happened: {summary['what_happened']} "
                f"What we did: {'; '.join(summary['what_we_did'])}."
                + (f" You approved: {'; '.join(approved)}." if approved else "")
                + f" {summary['confidence_text']} {summary['spot_it_next_time']} Reply REPORT for an FTC report.")
        self.send("summary", text, False)
        self.step("messaging", "summary", "message", "Incident summary sent by iMessage (no links)", {})

    async def go(self):
        self.case["run_running"] = True
        try:
            label = {"coached": "Sensitive action during an unverified call", "takeover": "SIM swap right after a new-device login",
                     "scam_text": "Customer forwarded a text to Titan"}.get(self.threat, self.trigger["type"])
            self.step("system", "trigger", "plan", label, {"event_id": self.trigger["event_id"]})
            await self.context()
            await self.risk()
            await self.verify()
            if self.case["threat"] == "legit":
                self.step("response", "respond", "plan", "Looks legitimate: no action, keep watching", {})
            elif await self.respond():
                outcome = await self.reach_and_wait()
                if outcome == "called":
                    await self.recover()
            if self.case["threat"] != "legit":
                await self.summarize()
            until = iso(now() + timedelta(hours=24))
            self.step("system", "watch", "plan", "Watching her line for 24 hours for follow-up scams", {"until": until})
            self.case["status"] = "watching"
            self.step("system", "watch", "done", "Run complete", {})
        except Exception as e:  # noqa: BLE001
            self.step("system", "watch", "error", f"Run failed: {type(e).__name__}: {e}", {})
            self.case["status"] = "watching"
            self.step("system", "watch", "done", "Run ended after an error", {})
        finally:
            self.case["run_running"] = False


TEMPLATES = {
    "alert": "Titan: {name}, you're on a call with a number we can't verify that says it's T-Mobile. We never ask you to turn off "
             "protection or share a transfer PIN on a call. Your number is safe and locked again. Was this your idea? Reply YES or NO.",
    "info": "Titan: We checked this for you. T-Mobile will never ask you for a PIN or code, or send you a link to verify your account.",
    "question": "Titan: Please hang up any call you're on, then reply YES or NO.",
    "summary": "Titan: We stepped in to keep your number safe. Your number is protected.",
}


def _sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return text
    text = text[0].upper() + text[1:]
    return text if text[-1] in ".!?" else text + "."


def apply_decision(store: Store, case: dict, action: dict, approve: bool, via: str):
    """Apply an approval/rejection to an action and its effect on the account (shared with the server)."""
    if not approve:
        action.update(status="rejected", approved_via=via if via in ("web", "sms", "voice") else "sms")
        store.add_step(case, new_id("run"), "voice" if via == "voice" else "messaging" if via == "sms" else "system", "recover",
                       "action", f"Declined via {via}: {action['description']}", {"action_id": action["action_id"], "approved": False})
        return action
    action.update(status="applied", approved_via=via if via in ("web", "sms", "voice") else "sms", applied_at=iso(now()))
    uid = case["user_id"]
    if action["kind"] == "revoke_transfer_pin":
        store.transfer_pins[uid] = {"status": "revoked", "hold_until": None}
    elif action["kind"] == "release_hold":
        store.transfer_pins[uid] = {"status": "active", "hold_until": None}
    store.add_step(case, new_id("run"), "voice" if via == "voice" else "messaging" if via == "sms" else "system", "recover", "approved",
                   f"Approved via {via}: {action['description']}", {"action_id": action["action_id"]})
    return action


async def run(store: Store, case: dict, threat: str, trigger: dict):
    await Run(store, case, threat, trigger).go()
