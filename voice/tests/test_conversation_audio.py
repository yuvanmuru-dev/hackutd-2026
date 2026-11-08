"""Real Pipecat input/turn/output pipeline; only hosted services are replaced."""
import base64
import threading
import time
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from service import create_app
from test_bridge import SID, probe_start, socket_headers
from test_conversation import ModelStub, VOICE_SETTINGS, setup_case


def wait_for(check):
    until = time.monotonic() + 8
    while time.monotonic() < until:
        if check():
            return
        time.sleep(.02)
    assert check(), "Pipeline did not reach its expected state"


def test_audio_turn_posts_transcripts_and_approves_only_the_finished_question(monkeypatch):
    from loguru import logger
    logger.remove()
    import bot
    from pipecat.frames.frames import InputAudioRawFrame, TranscriptionFrame, TTSAudioRawFrame, TTSStartedFrame
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.services.tts_service import TTSService
    from pipecat.serializers.twilio import TwilioFrameSerializer

    inputs = iter(["I need help", "Yes.", "End this call"])
    class SyntheticSTT(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, InputAudioRawFrame):
                await self.push_frame(TranscriptionFrame(next(inputs), "usr_maya", "", finalized=True))
            else:
                await self.push_frame(frame, direction)

    class SyntheticTTS(TTSService):
        async def run_tts(self, text, context_id):
            await self.create_audio_context(context_id)
            yield TTSStartedFrame(context_id=context_id)
            yield TTSAudioRawFrame(b"\x01\x00" * 1600, 8000, 1, context_id=context_id)

    monkeypatch.setattr(bot, "make_stt", lambda settings: SyntheticSTT())
    monkeypatch.setattr(bot, "make_tts", lambda settings: SyntheticTTS(sample_rate=8000))
    monkeypatch.setattr(TwilioFrameSerializer, "_hang_up_call", AsyncMock())
    _, request, brain = setup_case()
    models = ModelStub()
    provider = AsyncMock()
    provider.place.return_value = SID
    state = {}
    finished = threading.Event()
    async def run(ws, start, settings, controller, plan):
        state["controller"] = controller
        try:
            await bot.run_conversation(ws, start, settings, controller, plan)
        finally:
            finished.set()

    app = create_app(VOICE_SETTINGS, brain, call_provider=provider, model_provider=models,
        asr_check=AsyncMock(), conversation_runner=run)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        assert client.post("/internal/call", json=request).status_code == 202
        wait_for(lambda: provider.place.await_count)
        token = provider.place.await_args.args[1]
        with client.websocket_connect("/ws/bridge", headers=socket_headers()) as ws:
            ws.send_json({"event": "connected"})
            ws.send_json(probe_start(token))
            message = ws.receive_json()
            assert message["event"] == "media"
            assert base64.b64decode(message["media"]["payload"])
            wait_for(lambda: any(c.args[1] == "out" for c in brain.transcript.await_args_list))
            def say():
                ws.send_json({"event": "media", "media": {"payload": base64.b64encode(b"\xff" * 1600).decode()}})
            say()
            wait_for(lambda: state["controller"].heard_question)
            first = state["controller"].awaiting
            brain.decide.assert_not_awaited()
            say()
            wait_for(lambda: brain.decide.await_count)
            brain.decide.assert_awaited_once_with(first, True)
            wait_for(lambda: state["controller"].heard_question and state["controller"].awaiting != first)
            models.chosen_intent = "end"
            say()
            while ws.receive()["type"] != "websocket.close":
                pass
            assert finished.wait(5)
    incoming = [c.args[2] for c in brain.transcript.await_args_list if c.args[1] == "in"]
    assert incoming == ["I need help", "Yes.", "End this call"]
    brain.decide.assert_awaited_once()
