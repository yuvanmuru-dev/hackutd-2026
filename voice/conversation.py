"""Bounded voice dialogue; all facts, actions and approval decisions belong to the brain."""
from __future__ import annotations

from dataclasses import dataclass, field
import re

import httpx

from brain import Brain
from models import NvidiaModels, redact, speech_policy

HANG_UP = "If someone on another call is asking you to change account protection, please hang up on them. I'll stay on the line."
DISCLOSURE = "Did you share an account PIN, a login code, or a transfer PIN? Answer yes or no. Do not say any digits."
REFUSAL = "I will never ask for or read back a PIN, code, or password. Keep those private."
CLARIFY = "Please say yes or no for the single step I just asked about."
FAREWELL = "Thank you for speaking with Titan. Goodbye."
LABELS = {
    "relock": "turn account protection back on", "hold_transfer_pin": "keep the transfer PIN on hold",
    "require_step_up": "request an identity check in your account app", "reset_pin": "start an account PIN reset",
    "revoke_transfer_pin": "cancel the pending transfer PIN", "sign_out_sessions": "sign out other devices",
    "report_number": "report the suspicious number", "notify_trusted_contact": "notify your configured trusted contact",
    "send_ftc_report": "send the prepared FTC report", "release_hold": "request release of the transfer hold",
}
SAFE_RECOVERY = {"reset_pin", "revoke_transfer_pin", "sign_out_sessions", "report_number", "notify_trusted_contact"}


def words(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


def explicit_answer(text: str) -> bool | None:
    value = words(text)
    if value in {"yes", "yes please", "yes do that", "go ahead"}:
        return True
    if value in {"no", "no thanks", "no thank you", "do not"}:
        return False
    return None


@dataclass
class SpeechPlan:
    lines: list[str]
    action_id: str | None = None
    end: bool = False


@dataclass
class Conversation:
    request: dict
    brain: Brain
    models: NvidiaModels
    awaiting: str | None = None
    heard_question: bool = False
    expected_question: str = ""
    completed: set[str] = field(default_factory=set)
    last_plan: SpeechPlan | None = None
    disclosure_asked: bool = False
    history: list[dict] = field(default_factory=list)

    async def case(self) -> dict:
        detail = await self.brain.case(self.request["case_id"])
        if detail["user_id"] != self.request["user_id"] or detail["case_id"] != self.request["case_id"]:
            raise ValueError("Case does not belong to the requested user")
        return detail

    async def prepare(self, plan: SpeechPlan) -> SpeechPlan:
        # Every spoken candidate passes both the deterministic policy and NVIDIA
        # Safety Guard. No unapproved model-generated text can be spoken.
        plan.lines = [await self.models.guard(speech_policy(line)) for line in plan.lines]
        self.awaiting = plan.action_id
        self.heard_question = False
        self.expected_question = words(plan.lines[-1]) if plan.action_id else ""
        self.last_plan = plan
        return plan

    async def begin(self) -> SpeechPlan:
        detail = await self.case()
        pending = {a["action_id"] for a in detail["actions"] if a["status"] == "awaiting_approval"}
        if not set(self.request["pending_action_ids"]).issubset(pending):
            raise ValueError("Requested pending actions are not awaiting approval on this case")
        self.disclosure_asked = True
        return await self.prepare(SpeechPlan([self.request["opening_line"], HANG_UP, DISCLOSURE]))

    def heard(self, spoken_text: str, *, interrupted: bool = False) -> None:
        if spoken_text.strip():
            self.history.append({"role": "assistant", "content": redact(spoken_text)[:1024]})
            self.history = self.history[-8:]
        if interrupted:
            self.heard_question = False
        elif self.awaiting and self.expected_question and words(spoken_text).endswith(self.expected_question):
            self.heard_question = True

    async def next_action(self, prefix: list[str] | None = None, *, confirm: bool = False) -> SpeechPlan:
        detail = await self.case()
        for action in detail["actions"]:
            if action["status"] == "awaiting_approval" and action["action_id"] not in self.completed:
                label = LABELS.get(action["kind"])
                if label is None:
                    raise ValueError("No safe spoken label for pending action")
                # End at the question's natural answer point. A trailing spoken
                # instruction made a natural "yes" interrupt that instruction,
                # leaving the complete-question approval gate unarmed.
                question = ("Just to confirm, should I " if confirm else "Would you like me to ") + label + "?"
                return await self.prepare(SpeechPlan((prefix or []) + [question], action["action_id"]))
        return await self.prepare(SpeechPlan((prefix or []) + [
            "Your reply is recorded on this case. There is no recovery step waiting for approval right now. "
            "Please check your Messages for updates."]))

    async def turn(self, text: str) -> SpeechPlan:
        text = redact(text)
        await self.brain.transcript(self.request["case_id"], "in", text)
        answer = explicit_answer(text)
        intent, reply = "other", None
        if answer is None:
            try:
                detail = await self.case()
                pending = next((a for a in detail["actions"] if a["action_id"] == self.awaiting), None)
                result = await self.models.respond(text, self.request["facts"],
                    LABELS.get(pending["kind"], "") if pending else "", self.history)
                intent = result["intent"]
                if intent in {"yes", "no"}:
                    # The model's acknowledgement is not spoken. Only the
                    # guarded acknowledgement of the actual brain result is.
                    answer = intent == "yes"
                elif intent != "end":
                    reply = await self.models.guard(speech_policy(result["reply"]), facts=self.request["facts"])
            except Exception:
                # Model/guard failure cannot manufacture an approval. Keep the
                # already-guarded template path, including local secret refusal.
                intent = "secret" if re.search(r"\b(pin|code|password)\b", text, re.I) else "unclear"
                reply = None
        self.history.append({"role": "user", "content": text[:1024]})
        self.history = self.history[-8:]
        if self.awaiting and answer is not None:
            if not self.heard_question:
                return await self.next_action(["I'll repeat the question."])
            detail = await self.case()
            current = next((a for a in detail["actions"] if a["action_id"] == self.awaiting), None)
            if current is None or current["status"] != "awaiting_approval":
                return await self.next_action(["That step has changed. Let me check the current recovery plan."])
            if current["direction"] != "safer" or current["kind"] not in SAFE_RECOVERY:
                return await self.next_action(["The account protection cannot be loosened by voice. Please hang up on the other call first."])
            try:
                result = await self.brain.decide(self.awaiting, answer)
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 409:
                    return await self.next_action(["The account protection cannot be loosened right now. Please hang up on the other call first."])
                raise
            self.completed.add(self.awaiting)
            line = ("That step is complete." if result["status"] == "applied" else "Your approval is recorded.") if answer else "That step was declined."
            return await self.next_action([line])
        if self.awaiting and answer is None:
            # Nemotron may understand the utterance, but it can never turn an ambiguous
            # statement into approval. This remains one explicit answer per action.
            if intent == "secret":
                return await self.next_action([reply or REFUSAL])
            if intent == "end":
                return await self.prepare(SpeechPlan([FAREWELL], end=True))
            if intent == "question" and reply:
                return await self.next_action([reply])
            return await self.next_action(confirm=True)
        # Free-form replies are shared with the brain, which owns recovery planning.
        await self.brain.reply(self.request["case_id"], self.request["user_id"], text)
        if intent == "secret":
            return await self.next_action([reply or REFUSAL])
        if intent == "end":
            return await self.prepare(SpeechPlan([FAREWELL], end=True))
        if intent == "why":
            # Facts are read verbatim from the brain's already-verified CallRequest.
            facts = self.request["facts"]
            return await self.prepare(SpeechPlan(["Here is what the case reports.", *facts] if facts else [
                "I don't have verified details to read out. Please check your account app."]))
        if intent == "repeat" and self.last_plan:
            return await self.prepare(SpeechPlan(list(self.last_plan.lines), self.last_plan.action_id))
        return await self.next_action([reply or "Thank you. Do not share any secret digits with me."])
