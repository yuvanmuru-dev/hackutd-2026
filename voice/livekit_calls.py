"""D-050: Photon SIP calls through an isolated LiveKit room, never Twilio."""
import asyncio
from datetime import timedelta
import secrets

from config import phone


class LiveKitCalls:
    def __init__(self, settings, *, api_client=None, transport_factory=None, bot_runner=None):
        self.settings = settings
        self.api_client = api_client
        self.transport_factory = transport_factory
        self.bot_runner = bot_runner

    async def run(self, user_id, conversation=None, plan=None):
        from livekit import api
        from loguru import logger
        logger.remove()
        from pipecat.transports.livekit.transport import LiveKitTransport, LiveKitParams
        from bot import run_conversation, run_room_probe
        s = self.settings
        if user_id != "usr_maya" or phone(s.maya_number) not in s.allowlist:
            raise ValueError("No allowlisted teammate mapping for this user")
        if s.conversation_missing():
            raise ValueError("LiveKit conversation configuration is incomplete")
        lk = self.api_client or api.LiveKitAPI(s.livekit_url, s.livekit_key, s.livekit_secret)
        room = "titan-" + secrets.token_hex(12)
        task = None
        dial_task = None
        created = False
        try:
            trunks = await lk.sip.list_outbound_trunk(api.ListSIPOutboundTrunkRequest())
            trunk = next((t for t in trunks.items if t.sip_trunk_id == s.livekit_trunk), None)
            if (trunk is None or trunk.address != "sip.photon.codes:5061"
                    or trunk.transport != api.SIP_TRANSPORT_TLS or s.photon_number not in trunk.numbers
                    or trunk.auth_username != s.photon_sip_username):
                raise ValueError("Configured trunk is not the approved Photon TLS line")
            await lk.room.create_room(api.CreateRoomRequest(name=room, max_participants=2,
                empty_timeout=30, departure_timeout=10))
            created = True
            token = (api.AccessToken(s.livekit_key, s.livekit_secret).with_identity("titan-bot")
                .with_ttl(timedelta(minutes=5)).with_grants(api.VideoGrants(room_join=True,
                    room=room, can_publish=True, can_subscribe=True, can_publish_data=False)).to_jwt())
            factory = self.transport_factory or LiveKitTransport
            transport = factory(url=s.livekit_url, token=token, room_name=room,
                params=LiveKitParams(audio_in_enabled=conversation is not None,
                    audio_out_enabled=True, audio_in_user_tracks=False))
            ready, answered = asyncio.Event(), asyncio.Event()
            if self.bot_runner:
                run = self.bot_runner(transport, ready, answered)
            elif conversation is None:
                run = run_room_probe(transport, s, ready, answered)
            else:
                run = run_conversation(None, {}, s, conversation, plan,
                    transport_override=transport, ready=ready, answered=answered)
            task = asyncio.create_task(run)
            # A failed bot must never leave a ringing phone without an agent.
            waiter = asyncio.create_task(ready.wait())
            try:
                done, _ = await asyncio.wait({task, waiter}, timeout=25, return_when=asyncio.FIRST_COMPLETED)
                if task in done:
                    await task
                    raise RuntimeError("Bot exited before SIP dialing")
                if not ready.is_set():
                    raise TimeoutError("Bot did not join the room")
            finally:
                waiter.cancel()
                await asyncio.gather(waiter, return_exceptions=True)
            dial_task = asyncio.create_task(lk.sip.create_sip_participant(api.CreateSIPParticipantRequest(
                sip_trunk_id=s.livekit_trunk, sip_call_to=s.maya_number, sip_number=s.photon_number,
                room_name=room, participant_identity="maya", participant_name="Maya",
                hide_phone_number=True, wait_until_answered=True,
                ringing_timeout=timedelta(seconds=30), max_call_duration=timedelta(minutes=3)), timeout=40))
            done, _ = await asyncio.wait({task, dial_task}, return_when=asyncio.FIRST_COMPLETED)
            if task in done:
                await task
                raise RuntimeError("Bot exited while SIP was dialing")
            await dial_task
            answered.set()
            async with asyncio.timeout(180):
                await task
        finally:
            if dial_task:
                dial_task.cancel()
                await asyncio.gather(dial_task, return_exceptions=True)
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            try:
                if created:
                    await lk.room.delete_room(api.DeleteRoomRequest(room=room))
            finally:
                if self.api_client is None:
                    await lk.aclose()
