"""Titan's four agents (Context -> Risk -> Verifier -> Response) plus the reply reader and summary writer.

Each is a small, strict JSON prompt on Nemotron. Code around them enforces the rules (safer-only actions,
no links, never ask for a PIN), so a bad model answer can't loosen protection or stall the demo.
Agent model roles come from env: AGENT_CONTEXT_ROLE (default nano), AGENT_RISK_ROLE / AGENT_VERIFIER_ROLE (default super = Nemotron 3 Ultra),
AGENT_RESPONSE_ROLE (default nano = Lightning, customer words need speed), AGENT_REPLY_ROLE (default nano).
"""
from __future__ import annotations

import os
import re

from core import llm


def _role(agent: str, default: str) -> str:
    return os.getenv(f"AGENT_{agent.upper()}_ROLE", default)


RULES = ("You work for Titan, a scam-protection layer on top of T-Mobile's protections. "
         "Use only the facts given to you. Never invent numbers or events. "
         "Titan never asks a customer for a PIN, code or password and never sends links. "
         "Reply with ONLY one JSON object, no prose, no markdown.")

# ---------------- Context
CONTEXT_PLAN = RULES + """
You are the Context agent. A sensitive event happened on a customer's account. Decide which tools to call to understand it.
Input: {"trigger": event, "tools": [{"name","description"}]}
Output: {"plan": "one sentence, plain English", "tools": ["tool_name", ...]}  (3 to 7 tools, only names from the list)"""

CONTEXT_FACTS = RULES + """
You are the Context agent. Turn tool results into short facts a reviewer can check.
Input: {"trigger": event, "results": {"tool_name": {"summary", "result"}}}
Output: {"facts": [{"fact": "short sentence", "tool": "tool_name it came from"}]}  (3 to 8 facts; every fact must come from a tool's result)"""


def context_plan(trigger: dict, tool_list: list[dict]) -> tuple[dict, str]:
    return llm.chat_json(_role("context", "nano"), CONTEXT_PLAN, {"trigger": trigger, "tools": tool_list}, max_tokens=400)


def context_facts(trigger: dict, results: dict) -> tuple[dict, str]:
    slim = {k: {"summary": v.get("summary"), "result": v.get("result")} for k, v in results.items()}
    return llm.chat_json(_role("context", "nano"), CONTEXT_FACTS, {"trigger": trigger, "results": slim}, max_tokens=700)


# ---------------- Risk
RISK = RULES + """
You are the Risk agent. Decide what is happening and what Titan should do. Threats: takeover (someone else is in the account),
coached (the real customer is being talked into it by a scammer, often on a call), scam_text, bot, legit.
Input: {"trigger", "facts": [{"fact","tool"}], "score": {threat, probability, confidence, top_reasons}}
Output: {"threat": one of the threats, "decision": "allow"|"step_up_face"|"hold_and_alert"|"block",
         "assessment": "2 sentences in plain English for a fraud analyst",
         "claims": [{"claim": "short checkable sentence", "tool": "tool_name that proves it"}]}
Prefer the model score's threat unless the facts clearly contradict it. 2 to 5 claims."""


def risk(trigger: dict, facts: list[dict], score: dict) -> tuple[dict, str]:
    return llm.chat_json(_role("risk", "super"), RISK, {"trigger": trigger, "facts": facts, "score": score}, max_tokens=700)


# ---------------- Verifier
VERIFIER = RULES + """
You are the Verifier. Check each claim strictly against the raw tool results. A claim is supported only if a tool result shows it.
Input: {"claims": [{"claim","tool"}], "results": {"tool_name": {"result"}}}
Output: {"results": [{"index": 0, "supported": true|false, "note": "why, short"}]}  (one entry per claim, same order)"""


def verify(claims: list[dict], results: dict) -> tuple[dict, str]:
    slim = {k: {"result": v.get("result")} for k, v in results.items()}
    return llm.chat_json(_role("verifier", "super"), VERIFIER, {"claims": claims, "results": slim}, max_tokens=700)


# ---------------- Response (customer-facing words)
RESPONSE = RULES + """
You are the Response agent. Write what Titan says to the customer. Calm, short, plain words; the customer may be 68.
Speak to her directly as "you". No jargon (never say "coached", "attestation", "port-out", "STIR/SHAKEN"); say what happened plainly
(e.g. "someone on a call you can't verify asked you to turn off a protection").
Never blame her. Never ask for a PIN, code or password. No links. Confidence in words ("we're fairly sure, not certain").
Input: {"customer_name", "threat", "facts": [verified facts], "actions_taken": [strings], "on_call_now": bool}
Output: {"alert_text": "one iMessage under 320 characters that ends with 'Reply YES or NO.' asking if this was her idea",
         "call_opening_line": "first sentence Titan says when it calls her (introduce Titan, say it will never ask for a PIN or code)",
         "call_facts": ["3 short facts Titan can say on the call"]}"""


def response_text(name: str, threat: str, facts: list[str], actions: list[str], on_call: bool) -> tuple[dict, str]:
    return llm.chat_json(_role("response", "nano"), RESPONSE,
                         {"customer_name": name, "threat": threat, "facts": facts, "actions_taken": actions, "on_call_now": on_call},
                         max_tokens=500)


SUMMARY = RULES + """
You are the Response agent writing the incident summary the customer gets by iMessage after Titan stepped in.
Write to her as "you" (never her name in the third person). Plain words, no jargon ("coached", "attestation", "STIR/SHAKEN").
Input: {"customer_name", "case_number", "threat", "facts", "actions_taken", "customer_approved", "customer_declined", "customer_said"}
Output: {"what_happened": "1-2 sentences describing what the caller asked her to do", "why_we_stepped_in": "1-2 sentences",
         "confidence_text": "plain words, honest (fairly sure / not certain)",
         "next_steps": ["2-3 short things SHE should do now; never repeat actions already taken or approved"],
         "spot_it_next_time": "one sentence"}"""


def summary_text(payload: dict) -> tuple[dict, str]:
    return llm.chat_json(_role("response", "nano"), SUMMARY, payload, max_tokens=600)


# ---------------- Reply reader (messaging / voice answers)
REPLY = RULES + """
Classify the customer's reply to Titan.
Input: {"text": what she said, "question": what Titan asked}
Output: {"intent": "yes"|"no"|"help"|"report"|"undo"|"info", "shared": ["pin"|"code"|"transfer_pin"|"bank"], "note": "short"}
"yes" = she says it was her / agrees; "no" = it wasn't her / declines; "help" = she wants Titan to step in."""

_YES = re.compile(r"^\s*(yes|y|yeah|yep|it was me|that was me|approve|ok|okay)\b", re.I)
_NO = re.compile(r"^\s*(no|n|nope|not me|wasn'?t me|it wasn'?t me|decline|stop)\b", re.I)


def read_reply(text: str, question: str = "") -> dict:
    t = (text or "").strip()
    if t.upper() in ("REPORT", "UNDO"):
        return {"intent": t.lower(), "shared": [], "note": "keyword"}
    if _YES.match(t) and len(t) < 20:
        return {"intent": "yes", "shared": [], "note": "keyword"}
    if _NO.match(t) and len(t) < 25:
        return {"intent": "no", "shared": [], "note": "keyword"}
    try:
        out, _ = llm.chat_json(_role("reply", "nano"), REPLY, {"text": t, "question": question}, max_tokens=200)
        if out.get("intent") in ("yes", "no", "help", "report", "undo", "info"):
            out.setdefault("shared", [])
            return out
    except Exception:  # noqa: BLE001
        pass
    shared = [k for k, rx in (("pin", r"\bpin\b"), ("code", r"\bcode\b"), ("bank", r"\bbank\b")) if re.search(rx, t, re.I)]
    return {"intent": "info", "shared": shared, "note": "fallback"}


# ---------------- outbound guard (rules + optional Safety Guard)
_LINK = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(com|net|org|co|io|info|xyz|us)\b", re.I)
# A request aimed at the customer: "send/tell/give/read/share/enter/reply with ... your/me/us ... PIN/code/password",
# or a question asking for her PIN. Describing what the scammer asked her to do is not a request.
_ASKS_SECRET = re.compile(r"(?i)\b(send|tell|give|read|share|enter|reply with|text|confirm)\b(\s+(it|them))?\s+(me|us|titan)?\s*(your|the)\s+"
                          r"([a-z-]+\s+){0,2}(pin|passcode|password|code)\b|\bwhat(?:'s| is)\s+your\s+([a-z-]+\s+)?(pin|passcode|password|code)\b")


def outbound_ok(text: str, use_model: bool = True) -> tuple[bool, str]:
    if _LINK.search(text or ""):
        return False, "contains a link"
    for sentence in re.split(r"(?<=[.?!])\s+", text or ""):
        if _ASKS_SECRET.search(sentence) and not re.search(r"(?i)\b(never|don'?t|do not|won'?t|will not|not)\b", sentence):
            return False, "asks for a secret"
    if use_model and llm.model_for("safety"):
        try:
            out, _ = llm.chat_json("safety", "Assess this outbound message from a security service to a customer.", text, max_tokens=60)
            verdicts = [str(v).lower() for v in out.values()]  # Safety Guard v3: {"User Safety": "safe", ...}
            if out.get("safe") is False or any(v == "unsafe" for v in verdicts):
                return False, "Safety Guard flagged it"
        except Exception:  # noqa: BLE001
            return True, "Safety Guard unavailable; rules passed"
    return True, "ok"
