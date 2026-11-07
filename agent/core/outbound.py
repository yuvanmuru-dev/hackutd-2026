"""Brain -> doors. Records every outbound message/call in store.outbox and, if the door's URL is set,
POSTs it there (fire and forget). MESSAGING_URL -> /internal/send, VOICE_URL -> /internal/call.
"""
from __future__ import annotations

import os
import threading

import requests

from core.store import Store, iso, now


def _post(url: str, payload: dict, record: dict):
    try:
        r = requests.post(url, json=payload, timeout=5)
        record["delivery"] = f"http {r.status_code}"
    except Exception as e:  # door not running: the brain keeps going, the dashboard shows it
        record["delivery"] = f"failed: {type(e).__name__}"


def _dispatch(store: Store, kind: str, env: str, path: str, payload: dict) -> dict:
    record = {"kind": kind, "payload": payload, "ts": iso(now()), "delivery": "not sent (no door URL set)"}
    store.outbox.append(record)
    base = os.getenv(env)
    if base:
        record["delivery"] = "sending"
        threading.Thread(target=_post, args=(base.rstrip("/") + path, payload, record), daemon=True).start()
    return record


def send_message(store: Store, payload: dict) -> dict:
    return _dispatch(store, "send", "MESSAGING_URL", "/internal/send", payload)


def place_call(store: Store, payload: dict) -> dict:
    return _dispatch(store, "call", "VOICE_URL", "/internal/call", payload)
