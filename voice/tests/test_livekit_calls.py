import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from livekit_calls import LiveKitCalls
from test_conversation import VOICE_SETTINGS

LK = replace(VOICE_SETTINGS, voice_transport="livekit", livekit_url="wss://synthetic.livekit.cloud",
    livekit_key="synthetic-key", livekit_secret="synthetic-secret-for-token-signing",
    livekit_trunk="ST_synthetic", photon_number="+12025550103",
    photon_sip_username="synthetic-sip-user", photon_sip_password="synthetic-sip-password")


def client():
    from livekit import api
    lk = SimpleNamespace(sip=AsyncMock(), room=AsyncMock())
    lk.sip.list_outbound_trunk.return_value = SimpleNamespace(items=[api.SIPOutboundTrunkInfo(
        sip_trunk_id=LK.livekit_trunk, address="sip.photon.codes:5061",
        transport=api.SIP_TRANSPORT_TLS, numbers=[LK.photon_number], auth_username=LK.photon_sip_username)])
    return lk


def test_livekit_bot_joins_before_dial_and_room_is_deleted():
    async def run():
        lk = client()
        state = []
        async def bot(transport, ready, answered):
            state.append("joined")
            ready.set()
            await answered.wait()
            state.append("greeting")
        async def dial(req, **kwargs):
            assert state == ["joined"]
            assert req.sip_call_to == LK.maya_number
            assert req.sip_number == LK.photon_number
            assert req.wait_until_answered
            assert req.max_call_duration.seconds == 180
            assert req.ringing_timeout.seconds == 30
            assert req.hide_phone_number
            state.append("answered")
        lk.sip.create_sip_participant.side_effect = dial
        await LiveKitCalls(LK, api_client=lk, transport_factory=lambda **kw: object(), bot_runner=bot).run("usr_maya")
        assert state == ["joined", "answered", "greeting"]
        lk.room.delete_room.assert_awaited_once()
        assert lk.room.create_room.await_args.args[0].max_participants == 2
    asyncio.run(run())


def test_livekit_dial_failure_cleans_room_and_bot():
    async def run():
        lk = client()
        stopped = asyncio.Event()
        async def bot(transport, ready, answered):
            ready.set()
            try:
                await answered.wait()
            finally:
                stopped.set()
        lk.sip.create_sip_participant.side_effect = RuntimeError("synthetic SIP rejection")
        with pytest.raises(RuntimeError):
            await LiveKitCalls(LK, api_client=lk, transport_factory=lambda **kw: object(), bot_runner=bot).run("usr_maya")
        assert stopped.is_set()
        lk.room.delete_room.assert_awaited_once()
    asyncio.run(run())


def test_livekit_disallowed_number_never_touches_provider():
    async def run():
        lk = client()
        with pytest.raises(ValueError):
            await LiveKitCalls(replace(LK, allowlist=frozenset()), api_client=lk).run("usr_maya")
        lk.room.create_room.assert_not_awaited()
        lk.sip.create_sip_participant.assert_not_awaited()
    asyncio.run(run())


def test_livekit_configuration_requires_no_twilio_or_tunnel():
    assert replace(LK, account_sid="", auth_token="", twilio_number="", public_url="").conversation_missing() == []


def test_project_api_key_is_rejected_as_sip_password():
    assert any("not an API key" in error for error in
        replace(LK, photon_sip_password="pho_sk_synthetic").conversation_missing())


def test_provision_updates_configured_trunk_with_dedicated_sip_auth(monkeypatch):
    import livekit_setup
    from livekit import api
    lk = client()
    lk.aclose = AsyncMock()
    current = lk.sip.list_outbound_trunk.return_value.items[0]
    current.address = "sip.spectrum.photon.codes:5061"
    current.auth_username = "old-project-api-user"
    lk.sip.update_outbound_trunk_fields.return_value = api.SIPOutboundTrunkInfo(
        sip_trunk_id=LK.livekit_trunk, address="sip.photon.codes:5061",
        transport=api.SIP_TRANSPORT_TLS, numbers=[LK.photon_number], auth_username=LK.photon_sip_username)
    monkeypatch.setattr(livekit_setup.Settings, "from_env", lambda: LK)
    monkeypatch.setattr(livekit_setup.api, "LiveKitAPI", lambda *args: lk)
    monkeypatch.setattr(livekit_setup, "set_key", lambda *args: None)
    assert asyncio.run(livekit_setup.main("provision")) == 0
    lk.sip.update_outbound_trunk_fields.assert_awaited_once_with(LK.livekit_trunk,
        address="sip.photon.codes:5061", transport=api.SIP_TRANSPORT_TLS,
        numbers=[LK.photon_number], auth_username=LK.photon_sip_username, auth_password=LK.photon_sip_password)
    lk.sip.create_outbound_trunk.assert_not_awaited()
    lk.aclose.assert_awaited_once()


def test_bot_failure_while_dialing_cancels_call_and_deletes_room():
    async def run():
        lk = client()
        dialing = asyncio.Event()
        cancelled = asyncio.Event()
        async def bot(transport, ready, answered):
            ready.set()
            await dialing.wait()
            raise RuntimeError("synthetic bot failure")
        async def dial(*args, **kwargs):
            dialing.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        lk.sip.create_sip_participant.side_effect = dial
        with pytest.raises(RuntimeError):
            await LiveKitCalls(LK, api_client=lk, transport_factory=lambda **kw: object(), bot_runner=bot).run("usr_maya")
        assert cancelled.is_set()
        lk.room.delete_room.assert_awaited_once()
    asyncio.run(run())


def test_conversation_interlock_blocks_real_dispatch_until_brain_fix():
    from fastapi.testclient import TestClient
    from service import create_app
    from test_conversation import setup_case
    _, request, brain = setup_case()
    provider = AsyncMock()
    with TestClient(create_app(replace(LK, conversation_enabled=False), brain, call_provider=provider),
                    client=("127.0.0.1", 50000)) as c:
        assert c.post("/internal/call", json=request).status_code == 503
    provider.run.assert_not_awaited()
