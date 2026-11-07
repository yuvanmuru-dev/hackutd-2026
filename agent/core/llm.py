"""Model router for Titan's agents. NVIDIA endpoints only (D-015), OpenAI SDK as the client.

Roles -> (base URL env, model env, default model):
  super     Risk / Verifier / Response (Nemotron 3 Ultra)   NEMOTRON_BASE_URL, NEMOTRON_MODEL
  nano      Context, reply reading, fallback (Nemotron 3.5 Lightning)   NEMOTRON_BASE_URL, NEMOTRON_NANO_MODEL
  safety    Nemotron Safety Guard v3 on outbound text   SAFETY_MODEL (empty = rules only)
Model names verified against this account's /v1/models and live calls on 2026-11-07.

chat_json() retries 429/5xx/timeouts with backoff, falls back from super to nano, strips <think> blocks and
code fences, and parses the first JSON object. Tests inject a fake client with set_client().
"""
from __future__ import annotations

import json
import os
import re
import time

from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE = "https://integrate.api.nvidia.com/v1"
MODELS = {
    "super": ("NEMOTRON_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"),
    "nano": ("NEMOTRON_NANO_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b"),
    "safety": ("SAFETY_MODEL", "nvidia/llama-3.1-nemotron-safety-guard-8b-v3"),
}
_client = None
_calls: list[dict] = []  # last calls, for the dashboard/debug (model, ms, ok)


class LLMError(RuntimeError):
    pass


def set_client(client):
    """Inject a client (tests). Anything with .chat.completions.create(model=, messages=, ...)."""
    global _client
    _client = client


def client():
    global _client
    if _client is None:
        from openai import OpenAI
        key = os.getenv("NVIDIA_API_KEY")
        if not key:
            raise LLMError("NVIDIA_API_KEY is not set (agent/.env)")
        _client = OpenAI(base_url=os.getenv("NEMOTRON_BASE_URL", DEFAULT_BASE), api_key=key, timeout=45, max_retries=0)
    return _client


def model_for(role: str) -> str:
    env, default = MODELS[role]
    return os.getenv(env, default)


def recent_calls() -> list[dict]:
    return _calls[-20:]


_THINK = re.compile(r"<think>.*?</think>", re.S)


def parse_json(text: str):
    text = _THINK.sub("", text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise LLMError(f"no JSON in model output: {text[:200]!r}")
    depth, in_str, esc = 0, False, False
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            esc = (ch == "\\") and not esc
            if ch == '"' and not esc:
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise LLMError("unterminated JSON in model output")


def _retryable(e: Exception) -> bool:
    status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
    name = type(e).__name__
    return status in (429, 500, 502, 503, 504) or name in ("APITimeoutError", "APIConnectionError", "RateLimitError", "Timeout")


def chat(role: str, messages: list[dict], *, max_tokens: int = 900, temperature: float = 0.2) -> tuple[str, str]:
    """Returns (text, model_used). Retries, then falls back super -> nano."""
    chain = [role] + (["nano"] if role == "super" else [])
    last: Exception | None = None
    extra = {}
    if os.getenv("NEMOTRON_THINKING", "off") == "off":
        extra = {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
    for r in chain:
        model = model_for(r)
        if not model:
            continue
        for attempt in range(3):
            t0 = time.time()
            try:
                resp = client().chat.completions.create(model=model, messages=messages, max_tokens=max_tokens,
                                                        temperature=temperature, **extra)
                _calls.append({"model": model, "ms": int((time.time() - t0) * 1000), "ok": True})
                return resp.choices[0].message.content or "", model
            except Exception as e:  # noqa: BLE001
                _calls.append({"model": model, "ms": int((time.time() - t0) * 1000), "ok": False, "error": type(e).__name__})
                last = e
                if not _retryable(e):
                    break
                time.sleep(min(8, 1.5 * 2 ** attempt))
    raise LLMError(f"all models failed: {type(last).__name__}: {last}")


def chat_json(role: str, system: str, user: dict | str, *, max_tokens: int = 900) -> tuple[dict, str]:
    """System prompt + user payload (dict -> JSON) -> (parsed JSON, model_used). One repair retry on bad JSON."""
    content = user if isinstance(user, str) else json.dumps(user, default=str)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": content}]
    text, model = chat(role, messages, max_tokens=max_tokens)
    try:
        return parse_json(text), model
    except (LLMError, json.JSONDecodeError):
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "That was not valid JSON. Reply with ONLY the JSON object, nothing else."}]
        text, model = chat(role, messages, max_tokens=max_tokens)
        return parse_json(text), model
