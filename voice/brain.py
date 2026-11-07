"""Doors use the shared JSON Schema and HTTP only. No brain imports or local decisions."""
from __future__ import annotations

import json
from pathlib import Path

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
