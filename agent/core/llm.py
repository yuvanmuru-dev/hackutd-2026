"""Model router for Titan's agents. NVIDIA endpoints only (D-015), OpenAI SDK as the client.

Roles -> (base URL env, model env, default model):
  super     Risk / Verifier / Response (Nemotron 3 Ultra)   NEMOTRON_BASE_URL, NEMOTRON_MODEL
  nano      Context, reply reading, fallback (Nemotron 3.5 Lightning)   NEMOTRON_NANO_MODEL; optional self-hosted
            NEMOTRON_NANO_BASE_URL (+ NEMOTRON_NANO_SELF_MODEL, NEMOTRON_NANO_SELF_KEY) tried first, hosted as fallback
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
    "vision": ("NEMOTRON_VL_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b"),
}
_client = None
_calls: list[dict] = []  # last calls, for the dashboard/debug (model, ms, ok)


class LLMError(RuntimeError):
    pass


def set_client(client):
    """Inject a client (tests). Anything with .chat.completions.create(model=, messages=, ...)."""
    global _client
    _client = client


_clients: dict[tuple, object] = {}
_down_until: dict[str, float] = {}  # self-hosted endpoint -> time until which we skip it after a failure


def _client_for(base: str, key: str):
    if _client is not None:  # tests inject one fake client for every endpoint
        return _client
    if (base, key) not in _clients:
        from openai import OpenAI
        timeout = 45 if base == DEFAULT_BASE else 20
        _clients[(base, key)] = OpenAI(base_url=base, api_key=key or "not-needed", timeout=timeout, max_retries=0)
    return _clients[(base, key)]


def client():
    """Hosted NVIDIA client (kept for callers/tests that use it directly)."""
    key = os.getenv("NVIDIA_API_KEY")
    if _client is None and not key:
        raise LLMError("NVIDIA_API_KEY is not set (agent/.env)")
    return _client_for(os.getenv("NEMOTRON_BASE_URL", DEFAULT_BASE), key or "")


def targets(role: str) -> list[dict]:
    """Endpoints to try for a role, in order. NEMOTRON_NANO_BASE_URL (+ NEMOTRON_NANO_SELF_MODEL, NEMOTRON_NANO_SELF_KEY) points
    the fast role at a self-hosted Nemotron (e.g. a Brev NIM); the hosted API stays as the automatic fallback."""
    hosted_base = os.getenv("NEMOTRON_BASE_URL", DEFAULT_BASE)
    hosted_key = os.getenv("NVIDIA_API_KEY", "")
    out = []
    self_base = os.getenv("NEMOTRON_NANO_BASE_URL", "").rstrip("/")
    if role == "nano" and self_base and self_base != hosted_base.rstrip("/"):
        out.append({"base": self_base, "key": os.getenv("NEMOTRON_NANO_SELF_KEY", ""), "where": "self-hosted",
                    "model": os.getenv("NEMOTRON_NANO_SELF_MODEL") or model_for("nano")})
    if model_for(role):
        out.append({"base": hosted_base, "key": hosted_key, "where": "hosted", "model": model_for(role)})
    return out


def endpoints() -> dict:
    """For /health: where each role runs (hosts only, never keys)."""
    from urllib.parse import urlsplit
    res = {}
    for role in MODELS:
        res[role] = [{"where": t["where"], "host": urlsplit(t["base"]).netloc, "model": t["model"],
                      "skipping": _down_until.get(t["base"], 0) > time.time()} for t in targets(role)]
    return res


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


# ---------------------------------------------------------------- DEMO_MODE: record / replay model answers
# LLM_CACHE=record  -> every live answer is saved to LLM_CACHE_PATH
# DEMO_MODE=1 (or LLM_CACHE=replay) -> answer from the recording when the normalized prompt matches; otherwise call live
#                                      and save. Replays wait the recorded latency (capped by DEMO_REPLAY_MAX_MS) so the
#                                      dashboard still reads like a live run. The workflow labels replayed runs (honesty).
import hashlib  # noqa: E402
import threading  # noqa: E402

_cache_lock = threading.Lock()
_cache: dict | None = None
_stats = {"replayed": 0, "live": 0, "recorded": 0}
_ID = re.compile(r"\b(case|run|evt|act|msg|chk|call|ses|scn|usr)_[A-Za-z0-9_]+")
_TS = re.compile(r"\d{4}-\d{2}-\d{2}T[\d:.]+(Z|[+-]\d{2}:\d{2})?")
_DIGITS = re.compile(r"\d+")


def cache_mode() -> str:
    if os.getenv("DEMO_MODE", "0") == "1":
        return "replay"
    return os.getenv("LLM_CACHE", "off")


def cache_path() -> str:
    return os.getenv("LLM_CACHE_PATH") or os.path.join(os.path.dirname(__file__), "recordings", "llm_cache.json")


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(cache_path()) as f:
                _cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _cache = {}
    return _cache


def _save():
    path = cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_cache, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def _normalize(content) -> str:
    if isinstance(content, list):  # vision: hash the image instead of storing it
        parts = []
        for p in content:
            if p.get("type") == "image_url":
                parts.append("image:" + hashlib.sha256(p["image_url"]["url"].encode()).hexdigest()[:16])
            else:
                parts.append(_normalize(p.get("text", "")))
        return "|".join(parts)
    text = _ID.sub("<id>", str(content))
    text = _TS.sub("<ts>", text)
    return _DIGITS.sub("#", text)


def _key(role: str, messages: list[dict]) -> str:
    norm = json.dumps([[m["role"], _normalize(m["content"])] for m in messages])
    return hashlib.sha256(f"{role}|{norm}".encode()).hexdigest()


def cache_stats() -> dict:
    return {"mode": cache_mode(), "path": os.path.relpath(cache_path()), "entries": len(_load()), **_stats}


def chat(role: str, messages: list[dict], *, max_tokens: int = 900, temperature: float = 0.2) -> tuple[str, str]:
    """Returns (text, model_used). DEMO_MODE replay first; then live with retries and super -> nano fallback."""
    mode = cache_mode()
    key = _key(role, messages) if mode in ("record", "replay") else None
    if mode == "replay":
        with _cache_lock:
            hit = _load().get(key)
        if hit:
            _stats["replayed"] += 1
            time.sleep(min(hit.get("ms", 0), int(os.getenv("DEMO_REPLAY_MAX_MS", "2500"))) / 1000)
            _calls.append({"model": hit["model"], "ms": hit.get("ms", 0), "ok": True, "replayed": True})
            return hit["text"], hit["model"]
    t0 = time.time()
    text, model = _chat_live(role, messages, max_tokens=max_tokens, temperature=temperature)
    _stats["live"] += 1
    if key:
        with _cache_lock:
            _load()[key] = {"role": role, "model": model, "text": text, "ms": int((time.time() - t0) * 1000),
                            "prompt_head": _normalize(messages[0]["content"])[:60]}
            _save()
        _stats["recorded"] += 1
    return text, model


def _chat_live(role: str, messages: list[dict], *, max_tokens: int = 900, temperature: float = 0.2) -> tuple[str, str]:
    """Returns (text, model_used). Tries the role's endpoints in order (self-hosted first if configured, then hosted),
    with retries on 429/5xx/timeouts; super falls back to nano. A failing self-hosted box is skipped for 60 s."""
    chain = [role] + (["nano"] if role == "super" else [])  # vision has no text-only fallback
    last: Exception | None = None
    extra = {}
    if os.getenv("NEMOTRON_THINKING", "off") == "off":
        extra = {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
    for r in chain:
        for t in targets(r):
            if t["where"] == "self-hosted" and _down_until.get(t["base"], 0) > time.time():
                continue
            attempts = 3 if t["where"] == "hosted" else 1
            for attempt in range(attempts):
                t0 = time.time()
                try:
                    resp = _client_for(t["base"], t["key"]).chat.completions.create(
                        model=t["model"], messages=messages, max_tokens=max_tokens, temperature=temperature, **extra)
                    _calls.append({"model": t["model"], "where": t["where"], "ms": int((time.time() - t0) * 1000), "ok": True})
                    return resp.choices[0].message.content or "", t["model"]
                except Exception as e:  # noqa: BLE001
                    _calls.append({"model": t["model"], "where": t["where"], "ms": int((time.time() - t0) * 1000), "ok": False,
                                   "error": type(e).__name__})
                    last = e
                    if t["where"] == "self-hosted":
                        _down_until[t["base"]] = time.time() + 60  # box stopped or busy: use hosted for a minute
                        break
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
