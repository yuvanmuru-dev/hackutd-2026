"""Doors use the shared JSON Schema and HTTP only. No brain imports or local decisions."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote
import uuid

import httpx
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "contracts/schema.json").read_text(encoding="utf-8"))


def validate(name: str, payload: dict) -> dict:
    Draft202012Validator(
        {"$ref": f"#/$defs/{name}", "$defs": SCHEMA["$defs"]},
        format_checker=FormatChecker(),
    ).validate(payload)
    return payload


class Brain:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def event(self, payload: dict) -> None:
        response = await self.client.post("/events", json=validate("Event", payload))
        response.raise_for_status()

    async def health(self) -> None:
        response = await self.client.get("/health")
        response.raise_for_status()
        if response.json().get("ok") is not True:
            raise ValueError("Brain is not ready")

    async def case(self, case_id: str) -> dict:
        response = await self.client.get("/cases/" + quote(case_id, safe=""))
        response.raise_for_status()
        return validate("CaseDetail", response.json())

    async def transcript(self, case_id: str, direction: str, text: str) -> None:
        payload = validate("CaseEventRequest", {"channel": "voice", "direction": direction,
            "kind": "transcript", "text": text[:4096], "agent": "voice"})
        response = await self.client.post("/cases/" + quote(case_id, safe="") + "/events", json=payload)
        response.raise_for_status()

    async def reply(self, case_id: str, user_id: str, text: str) -> None:
        await self.event({"event_id": "evt_voice_reply_" + uuid.uuid4().hex,
            "user_id": user_id, "type": "customer.reply", "ts": datetime.now(timezone.utc).isoformat(),
            "source": "voice", "data": {"channel": "voice", "text": text[:4096], "case_id": case_id}})

    async def decide(self, action_id: str, approve: bool) -> dict:
        payload = validate("ApprovalRequest", {"via": "voice"})
        response = await self.client.post("/actions/" + quote(action_id, safe="") + ("/approve" if approve else "/reject"), json=payload)
        response.raise_for_status()
        return validate("Action", response.json())

    async def delivery(self, case_id: str, text: str) -> None:
        payload = validate("CaseEventRequest", {"channel": "voice", "direction": "out",
            "kind": "delivery", "text": text[:4096], "agent": "voice"})
        response = await self.client.post("/cases/" + quote(case_id, safe="") + "/events", json=payload)
        response.raise_for_status()
