"""Offline protocol/safety checks with synthetic teammate numbers and signed callbacks."""
from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import AsyncMock
import xml.etree.ElementTree as ET

from fastapi.testclient import TestClient
import httpx
import pytest
from starlette.websockets import WebSocketDisconnect
from twilio.request_validator import RequestValidator

from brain import validate
from config import Settings
from service import create_app

CALLER = "+12025550101"
MAYA = "+12025550102"
TWILIO = "+12025550103"
ACCOUNT = "AC" + "0" * 32
SID = "CA" + "1" * 32
SETTINGS = Settings(voice_transport="twilio", conversation_enabled=True, public_url="https://voice.example.test", account_sid=ACCOUNT,
                    auth_token="synthetic-test-token", twilio_number=TWILIO, maya_number=MAYA,
                    allowlist=frozenset({CALLER, MAYA}), hash_salt="synthetic-test-salt",
                    probe_enabled=True, elevenlabs_key="synthetic-key", elevenlabs_voice="synthetic-voice")


def post(client, path, **fields):
    fields = {"AccountSid": ACCOUNT, **fields}
    signature = RequestValidator(SETTINGS.auth_token).compute_signature(SETTINGS.public_url + path, fields)
    return client.post(path, data=fields, headers={"X-Twilio-Signature": signature})


def incoming(client):
    return post(client, "/webhooks/twilio/inbound", CallSid=SID, From=CALLER)


def status(client, value="in-progress", duration="0"):
    return post(client, "/webhooks/twilio/forward-status", ParentCallSid=SID,
                CallSid="CA" + "2" * 32, CallStatus=value, CallDuration=duration)


def test_health_works_without_keys_and_does_not_claim_intervention_ready():
    with TestClient(create_app(Settings())) as client:
        data = client.get("/health").json()
        assert data["ok"] is True
        assert data["intervention_ready"] is False
        assert "TWILIO_AUTH_TOKEN" in data["forwarding_configuration_required"]
        assert client.post("/webhooks/twilio/inbound", data={}).status_code == 503


def test_forged_signature_and_wrong_account_are_rejected():
    with TestClient(create_app(SETTINGS)) as client:
        assert client.post("/webhooks/twilio/inbound", data={"From": CALLER}).status_code == 401
        assert post(client, "/webhooks/twilio/inbound", AccountSid="unexpected", From=CALLER).status_code == 401


def test_only_teammates_can_be_forwarded_and_there_is_no_media_stream():
    brain = AsyncMock()
    with TestClient(create_app(SETTINGS, brain)) as client:
        root = ET.fromstring(incoming(client).text)
        assert root.find("Dial").attrib["record"] == "do-not-record"
        assert root.find("Dial/Number").text == MAYA
        assert root.find(".//Stream") is None
        assert root.find(".//Record") is None
        assert root.find(".//Gather") is None
        assert root.find("Dial/Number").attrib["statusCallbackEvent"] == "answered completed"
        assert ET.fromstring(post(client, "/webhooks/twilio/inbound", CallSid=SID, From="+12025550199").text).find("Reject") is not None
        brain.event.assert_not_awaited()  # Ringing is not yet an active call.


@pytest.mark.parametrize("changes", [{"maya_number": "+12025550199"}, {"maya_number": TWILIO}, {"public_url": "http://unsafe.test"}])
def test_unsafe_forwarding_configuration_is_blocked(changes):
    settings = replace(SETTINGS, **changes)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["forwarding_configuration_required"]


def test_start_end_are_contract_valid_hashed_and_deduplicated():
    brain = AsyncMock()
    with TestClient(create_app(SETTINGS, brain)) as client:
        assert incoming(client).status_code == 200
        for value in ["in-progress", "in-progress", "completed", "completed", "in-progress"]:
            assert status(client, value, "19").status_code == 204
    events = [c.args[0] for c in brain.event.await_args_list]
    assert [e["type"] for e in events] == ["call.started", "call.ended"]
    assert events[0]["call_id"] == events[1]["call_id"]
    for e in events:
        validate("Event", e)
        assert CALLER not in json.dumps(e)
        assert SID not in json.dumps(e)
    assert events[1]["data"] == {"duration_s": 19}


def test_completed_before_answered_does_not_reopen_call():
    brain = AsyncMock()
    with TestClient(create_app(SETTINGS, brain)) as client:
        incoming(client)
        assert status(client, "completed", "27").status_code == 204
        assert status(client, "in-progress").status_code == 204
    assert [c.args[0]["type"] for c in brain.event.await_args_list] == ["call.started", "call.ended"]


def test_unanswered_call_never_starts_a_window():
    brain = AsyncMock()
    with TestClient(create_app(SETTINGS, brain)) as client:
        incoming(client)
        assert status(client, "busy").status_code == 204
        assert status(client, "in-progress").status_code == 204
    brain.event.assert_not_awaited()


def test_failed_brain_delivery_retries_same_event_id():
    brain = AsyncMock()
    brain.event.side_effect = [httpx.ConnectError("synthetic failure"), None]
    with TestClient(create_app(SETTINGS, brain)) as client:
        incoming(client)
        assert status(client).status_code == 503
        assert status(client).status_code == 204
    first, second = [c.args[0] for c in brain.event.await_args_list]
    assert first == second


def test_unknown_callback_never_invents_a_call():
    with TestClient(create_app(SETTINGS, AsyncMock())) as client:
        assert status(client).status_code == 409


def test_malformed_duration_is_rejected_before_delivery():
    brain = AsyncMock()
    with TestClient(create_app(SETTINGS, brain)) as client:
        incoming(client)
        assert status(client, "completed", "not-a-number").status_code == 422
    brain.event.assert_not_awaited()


def probe_start(token, **overrides):
    return {"event": "start", "start": {"accountSid": ACCOUNT, "callSid": SID,
            "streamSid": "MZ" + "3" * 32, "customParameters": {"bridge_token": token},
            "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1}, **overrides}}


def socket_headers():
    return {"X-Twilio-Signature": RequestValidator(SETTINGS.auth_token).compute_signature(
        "wss://voice.example.test/ws/bridge", {})}


def test_probe_requires_explicit_enablement_and_never_accepts_a_forwarded_call():
    with TestClient(create_app(replace(SETTINGS, probe_enabled=False))) as client:
        assert post(client, "/webhooks/twilio/bridge-probe", CallSid=SID, From=CALLER).status_code == 404
    with TestClient(create_app(SETTINGS)) as client:
        incoming(client)
        assert post(client, "/webhooks/twilio/bridge-probe", CallSid=SID, From=CALLER).status_code == 409


def test_websocket_requires_provider_signature():
    with TestClient(create_app(SETTINGS)) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/bridge"):
                pass


def test_websocket_grant_is_bound_to_call_and_single_use():
    async def runner(ws, start, settings):
        await ws.send_json({"probe": "accepted"})
        await ws.close()

    with TestClient(create_app(SETTINGS, probe_runner=runner)) as client:
        response = post(client, "/webhooks/twilio/bridge-probe", CallSid=SID, From=CALLER)
        root = ET.fromstring(response.text)
        token = root.find(".//Parameter").attrib["value"]
        for override, accepted in [({"callSid": "different-call"}, False), ({}, True), ({}, False)]:
            with client.websocket_connect("/ws/bridge", headers=socket_headers()) as ws:
                ws.send_json({"event": "connected"})
                ws.send_json(probe_start(token, **override))
                if accepted:
                    assert ws.receive_json() == {"probe": "accepted"}
                else:
                    with pytest.raises(WebSocketDisconnect):
                        ws.receive_json()


def test_call_fixture_contract_is_shared_without_local_shape_changes():
    path = Path(__file__).resolve().parents[2] / "contracts/fixtures/callreq.t2.json"
    validate("CallRequest", json.loads(path.read_text(encoding="utf-8")))


def test_metadata_forwarding_updates_actual_mock_brain(monkeypatch):
    # Tests use the existing MOCK brain through HTTP, never a door-local fake.
    import sys
    import asyncio
    monkeypatch.setenv("MOCK", "1")
    monkeypatch.delenv("MESSAGING_URL", raising=False)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "agent"))
    import server
    from core.store import store
    from brain import Brain

    store.reset()
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://brain.test") as client:
            real_brain = Brain(client)
            # ASGI HTTP keeps provider delivery and the real brain on the same loop.
            app = create_app(SETTINGS, real_brain)
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://voice.test") as voice:
                    async def send(path, **fields):
                        fields = {"AccountSid": ACCOUNT, **fields}
                        sig = RequestValidator(SETTINGS.auth_token).compute_signature(SETTINGS.public_url + path, fields)
                        return await voice.post(path, data=fields, headers={"X-Twilio-Signature": sig})
                    assert (await send("/webhooks/twilio/inbound", CallSid=SID, From=CALLER)).status_code == 200
                    assert (await send("/webhooks/twilio/forward-status", ParentCallSid=SID, CallStatus="in-progress")).status_code == 204
                    assert (await client.get("/protections/usr_maya")).json()["shield_mode"] is True
                    timeline = (await client.get("/users/usr_maya/timeline")).json()
                    assert timeline["active_call"]["attestation"] == "C"
                    assert (await send("/webhooks/twilio/forward-status", ParentCallSid=SID, CallStatus="completed", CallDuration="12")).status_code == 204
                    assert (await client.get("/protections/usr_maya")).json()["shield_mode"] is False
                    assert len((await client.get("/users/usr_maya/timeline")).json()["events"]) == 2
    try:
        asyncio.run(run())
    finally:
        store.reset()
