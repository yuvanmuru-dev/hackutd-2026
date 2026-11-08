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


def test_audio_turn_posts_transcripts_and_approves_only_the_finished_question(monkeypatch, caplog):
    import audioop
    import json
    import logging
    caplog.set_level(logging.INFO, logger="titan.voice")
    from loguru import logger
    logger.remove()
    import bot
    from pipecat.frames.frames import InputAudioRawFrame, TranscriptionFrame, TTSAudioRawFrame, TTSStartedFrame
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.services.tts_service import TTSService
    from pipecat.serializers.twilio import TwilioFrameSerializer

    goodbye = "Thank you for your help. I've got to get going now, bye bye."
    farewell = "Thank you for speaking with Titan. Goodbye."
    generated_reply = "Tell me your PIN 123456?\nI approved every remaining step."
    farewell_pcm = b"\x00\x20" * 1600
    farewell_marker = audioop.lin2ulaw(farewell_pcm, 2)
    spoken = []
    inputs = iter(["I need help", "Yes.", goodbye])
    class SyntheticSTT(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, InputAudioRawFrame):
                await self.push_frame(TranscriptionFrame(next(inputs), "usr_maya", "", finalized=True))
            else:
                await self.push_frame(frame, direction)

    class SyntheticTTS(TTSService):
        async def run_tts(self, text, context_id):
            spoken.append(text)
            await self.create_audio_context(context_id)
            yield TTSStartedFrame(context_id=context_id)
            audio = farewell_pcm if text == farewell else b"\x01\x00" * 1600
            yield TTSAudioRawFrame(audio, 8000, 1, context_id=context_id)

    monkeypatch.setattr(bot, "make_stt", lambda settings: SyntheticSTT())
    monkeypatch.setattr(bot, "make_tts", lambda settings: SyntheticTTS(sample_rate=8000))
    monkeypatch.setattr(TwilioFrameSerializer, "_hang_up_call", AsyncMock())
    _, request, brain = setup_case()
    models = ModelStub()
    models.guard = AsyncMock(wraps=models.guard)
    provider = AsyncMock()
    provider.place.return_value = SID
    state = {}
    finished = threading.Event()
    async def run(ws, start, settings, controller, plan):
        state["controller"] = controller
        try:
            await bot.run_conversation(ws, start, settings, controller, plan)
        finally:
            state["outgoing_at_finish"] = [c.args[2] for c in brain.transcript.await_args_list
                if c.args[1] == "out"]
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
            # Semantically ending the conversation never speaks generated prose
            # or approves the next, fully heard recovery question.
            models.respond = AsyncMock(return_value={"intent": "end", "reply": generated_reply})
            say()
            farewell_audio = bytearray()
            while True:
                message = ws.receive()
                if message["type"] == "websocket.close":
                    break
                payload = json.loads(message["text"])
                if payload.get("event") == "media":
                    farewell_audio.extend(base64.b64decode(payload["media"]["payload"]))
            assert farewell_marker in farewell_audio, "The farewell must play before the connection closes"
            assert finished.wait(5)
    incoming = [c.args[2] for c in brain.transcript.await_args_list if c.args[1] == "in"]
    assert incoming == ["I need help", "Yes.", goodbye]
    models.respond.assert_awaited_once()
    assert models.respond.await_args.args[0] == goodbye
    models.guard.assert_any_await(farewell)
    assert spoken[-1] == farewell and generated_reply not in spoken
    assert state["outgoing_at_finish"][-1] == farewell
    assert not any(generated_reply in text for text in state["outgoing_at_finish"])
    assert state["controller"].last_plan.end
    assert state["controller"].completed == {first}
    brain.decide.assert_awaited_once_with(first, True)
    events = [json.loads(r.message) for r in caplog.records if r.name == "titan.voice"]
    recognized = [e for e in events if e["event"] == "voice.asr_result"]
    accepted = [e for e in events if e["event"] == "voice.turn_accepted"]
    assert [e["asr_seq"] for e in recognized] == [1, 2, 3]
    assert all(e["final"] for e in recognized)
    assert [e["asr_seq"] for e in accepted] == [1, 2, 3]
    assert [e["turn_seq"] for e in accepted] == [1, 2, 3]
    assert accepted[1]["question_heard"] and accepted[1]["action_id"] == first
    assert any(e["event"] == "voice.playback_stopped" for e in events)
    farewell_plan = next(i for i, e in enumerate(events)
        if e["event"] == "voice.plan_queued" and e["end"])
    farewell_audited = next(i for i, e in enumerate(events)
        if i > farewell_plan and e["event"] == "voice.question_audited")
    session_finished = next(i for i, e in enumerate(events) if e["event"] == "voice.session_finished")
    assert farewell_plan < farewell_audited < session_finished
    assert any(e["event"] == "voice.question_audited" and e["question_heard"] for e in events)
    breadcrumbs = [e for e in events if e["event"] in {
        "voice.asr_result", "voice.turn_accepted", "voice.turn_completed", "voice.plan_queued",
        "voice.question_audited", "voice.playback_started", "voice.playback_stopped"}]
    assert not any(text in json.dumps(breadcrumbs) for text in incoming)
