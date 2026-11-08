"""Outbound provider boundary checks without contacting Twilio."""
import asyncio
from dataclasses import replace
from urllib.parse import parse_qs
import xml.etree.ElementTree as ET

import httpx
import pytest

from config import Settings
from telephony import TwilioCalls
from test_bridge import SID
from test_conversation import VOICE_SETTINGS


def test_outbound_call_uses_allowlisted_mapping_and_never_records():
    async def run():
        def provider(request):
            data = parse_qs(request.content.decode())
            assert data["To"] == [VOICE_SETTINGS.maya_number]
            assert data["From"] == [VOICE_SETTINGS.twilio_number]
            assert data["Record"] == ["false"]
            assert data["StatusCallbackEvent"] == ["initiated", "ringing", "answered", "completed"]
            assert data["StatusCallback"] == [VOICE_SETTINGS.public_url + "/webhooks/twilio/intervention-status?request=synthetic-token"]
            stream = ET.fromstring(data["Twiml"][0]).find("./Connect/Stream")
            assert stream.attrib["url"] == "wss://voice.example.test/ws/bridge"
            assert stream.find("Parameter").attrib == {"name": "bridge_token", "value": "synthetic-token"}
            return httpx.Response(201, json={"sid": SID})
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
            assert await TwilioCalls(client, VOICE_SETTINGS).place("usr_maya", "synthetic-token") == SID
    asyncio.run(run())


def test_non_allowlisted_destination_never_reaches_provider():
    async def run():
        def provider(request):
            pytest.fail("A disallowed call reached the provider")
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
            with pytest.raises(ValueError):
                await TwilioCalls(client, replace(VOICE_SETTINGS, allowlist=frozenset())).place("usr_maya", "token")
    asyncio.run(run())


def test_d035_environment_name_selects_approved_model(monkeypatch):
    monkeypatch.setenv("NEMOTRON_VOICE_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
    monkeypatch.setenv("VOICE_LLM_MODEL", "obsolete-name-must-not-win")
    assert Settings.from_env().llm_model == "nvidia/nemotron-3.5-lightning-30b-a3b"
