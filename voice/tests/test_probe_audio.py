"""Exercise the actual Pipecat transport/serializer with synthetic tone audio."""
import base64
from unittest.mock import AsyncMock
import xml.etree.ElementTree as ET

from fastapi.testclient import TestClient
from loguru import logger

from test_bridge import SETTINGS, SID, CALLER, post, probe_start, socket_headers
from service import create_app


def test_probe_produces_twilio_media_and_drains_before_hanging_up(monkeypatch):
    logger.remove()
    from pipecat.frames.frames import TTSAudioRawFrame, TTSStartedFrame
    from pipecat.services.tts_service import TTSService
    from pipecat.serializers.twilio import TwilioFrameSerializer
    import bot

    class SyntheticTTS(TTSService):
        async def run_tts(self, text, context_id):
            await self.create_audio_context(context_id)
            yield TTSStartedFrame(context_id=context_id)
            yield TTSAudioRawFrame(b"\x01\x00" * 1600, 8000, 1, context_id=context_id)

    monkeypatch.setattr(bot, "make_tts", lambda settings: SyntheticTTS(sample_rate=8000))
    hang_up = AsyncMock()
    monkeypatch.setattr(TwilioFrameSerializer, "_hang_up_call", hang_up)
    with TestClient(create_app(SETTINGS)) as client:
        response = post(client, "/webhooks/twilio/bridge-probe", CallSid=SID, From=CALLER)
        token = ET.fromstring(response.text).find(".//Parameter").attrib["value"]
        with client.websocket_connect("/ws/bridge", headers=socket_headers()) as ws:
            ws.send_json({"event": "connected"})
            ws.send_json(probe_start(token))
            message = ws.receive_json()
            assert message["event"] == "media"
            assert message["streamSid"] == "MZ" + "3" * 32
            assert base64.b64decode(message["media"]["payload"])
            while ws.receive()["type"] != "websocket.close":
                pass
    hang_up.assert_awaited_once()
