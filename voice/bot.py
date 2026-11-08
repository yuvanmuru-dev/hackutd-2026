"""Pipecat bridge probe and Titan-only intervention conversation. No scam audio."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from config import Settings

GREETING = "Hello. This is the Titan voice bridge test. I will never ask you for a PIN or a code."


def make_tts(settings: Settings):
    # Lazy imports keep health and metadata forwarding usable without model access.
    if settings.tts_provider == "elevenlabs":
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
        return ElevenLabsTTSService(
            api_key=settings.elevenlabs_key, sample_rate=8000,
            settings=ElevenLabsTTSService.Settings(
                model="eleven_flash_v2_5", voice=settings.elevenlabs_voice,
            ),
        )
    if settings.tts_provider == "magpie":
        from pipecat.services.nvidia.tts import NvidiaTTSService
        from pipecat.transcriptions.language import Language
        return NvidiaTTSService(
            api_key=settings.nvidia_key, sample_rate=8000,
            settings=NvidiaTTSService.Settings(voice=settings.magpie_voice, language=Language.EN_US),
        )
    raise ValueError("TTS_PROVIDER must be elevenlabs or magpie")


def make_stt(settings: Settings):
    from pipecat.services.nvidia.stt import NvidiaSTTService
    from pipecat.transcriptions.language import Language
    from models import ASR_FUNCTION_ID
    return NvidiaSTTService(api_key=settings.nvidia_key, sample_rate=16000,
        model_function_map={"function_id": ASR_FUNCTION_ID, "model_name": "nemotron-asr-streaming"},
        settings=NvidiaSTTService.Settings(language=Language.EN_US, interim_results=True))


async def run_probe(websocket, start: dict, settings: Settings):
    """Play a labeled greeting through Pipecat and close after draining the audio."""
    from pipecat.frames.frames import BotStartedSpeakingFrame, EndFrame, TTSSpeakFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
    from pipecat.observers.base_observer import BaseObserver
    from pipecat.observers.service_metrics_observer import ServiceMetricsObserver
    from pipecat.workers.runner import WorkerRunner
    from pipecat.serializers.twilio import TwilioFrameSerializer
    from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport

    # Strip framework logs before constructing any processor. Providers can log text
    # and raw exception URLs; operational logs below contain metadata only.
    from loguru import logger
    logger.remove()
    from service import emit
    import time
    import traceback

    started = time.monotonic()
    class ProbeObserver(BaseObserver):
        def __init__(self):
            super().__init__(observe_every_push=False)
            self.audio_sent = False

        async def on_push_frame(self, data):
            if isinstance(data.frame, BotStartedSpeakingFrame) and not self.audio_sent:
                self.audio_sent = True
                emit("bridge.first_audio_sent", stage="transport", endpoint=settings.tts_provider,
                     observed_ms=round((time.monotonic() - started) * 1000))

    observer = ProbeObserver()
    metrics = ServiceMetricsObserver()

    @metrics.event_handler("on_service_latency")
    async def latency(observer, record):
        emit("bridge.service_latency", stage="tts", kind=record.kind,
             observed_ms=round(record.seconds * 1000), endpoint=settings.tts_provider)
    serializer = TwilioFrameSerializer(
        stream_sid=start["streamSid"], call_sid=start["callSid"],
        account_sid=settings.account_sid, auth_token=settings.auth_token,
    )
    transport = FastAPIWebsocketTransport(websocket, params=FastAPIWebsocketParams(
        audio_in_enabled=False, audio_out_enabled=True, add_wav_header=False,
        serializer=serializer, session_timeout=30,
    ))
    tts = make_tts(settings)
    worker = PipelineWorker(Pipeline([transport.input(), tts, transport.output()]),
                            enable_rtvi=False, observers=[observer, metrics],
                            processor_unusable_policy=ProcessorUnusablePolicy.CANCEL,
                            params=PipelineParams(audio_in_sample_rate=8000, audio_out_sample_rate=8000,
                                                  enable_metrics=True))
    runner = WorkerRunner(handle_sigint=False)
    failures = []

    @worker.event_handler("on_pipeline_error")
    async def pipeline_error(worker, frame):
        category = frame.category.value
        failures.append(category)
        emit("bridge.provider_error", stage="tts", category=category, endpoint=settings.tts_provider)

    @transport.event_handler("on_client_connected")
    async def connected(transport, websocket):
        emit("bridge.pipeline_started", transport="twilio", stage="tts", endpoint=settings.tts_provider)
        await worker.queue_frames([TTSSpeakFrame(GREETING), EndFrame()])

    @transport.event_handler("on_client_disconnected")
    async def disconnected(transport, websocket):
        await runner.cancel()

    @transport.event_handler("on_session_timeout")
    async def timed_out(transport, websocket):
        emit("bridge.timeout", stage="transport")
        await runner.cancel()

    try:
        await runner.add_workers(worker)
        await runner.run()
        if failures or not observer.audio_sent:
            raise RuntimeError("No successful audio output from bridge probe")
    except Exception as error:
        emit("bridge.failed", stage="tts_or_transport", exception_type=type(error).__name__,
             traceback=[{"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                        for f in traceback.extract_tb(error.__traceback__)])
        raise RuntimeError("Bridge probe failed; inspect provider diagnostics without exposing call data") from None
    finally:
        emit("bridge.session_finished", stage="transport", duration_ms=round((time.monotonic() - started) * 1000))


async def run_conversation(websocket, start: dict, settings: Settings, conversation, initial_plan):
    """Only an authenticated, call-bound intervention grant reaches this pipeline."""
    from loguru import logger
    logger.remove()
    import time
    from service import emit
    from models import redact
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.frames.frames import (BotStartedSpeakingFrame, BotStoppedSpeakingFrame, EndFrame,
        InterruptionFrame, InterimTranscriptionFrame, LLMContextFrame, TTSSpeakFrame, TTSTextFrame, TranscriptionFrame)
    from pipecat.observers.base_observer import BaseObserver
    from pipecat.observers.service_metrics_observer import ServiceMetricsObserver
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair, LLMUserAggregatorParams
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.serializers.twilio import TwilioFrameSerializer
    from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport
    from pipecat.workers.runner import WorkerRunner
    from pipecat.turns.user_turn_strategies import UserTurnStrategies
    from pipecat.turns.user_stop import SpeechTimeoutUserTurnStopStrategy

    started = time.monotonic()
    cid = conversation.request["case_id"]
    transport = FastAPIWebsocketTransport(websocket, params=FastAPIWebsocketParams(
        audio_in_enabled=True, audio_out_enabled=True, add_wav_header=False, session_timeout=300,
        serializer=TwilioFrameSerializer(stream_sid=start["streamSid"], call_sid=start["callSid"],
            account_sid=settings.account_sid, auth_token=settings.auth_token)))
    output = transport.output()

    class RedactionProcessor(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, (TranscriptionFrame, InterimTranscriptionFrame)):
                frame.text = redact(frame.text)
            await self.push_frame(frame, direction)

    class DialogueProcessor(FrameProcessor):
        async def speak(self, plan):
            for line in plan.lines:
                await self.push_frame(TTSSpeakFrame(line))
            if plan.end:
                # End from the worker's input so the microphone transport and
                # ASR also shut down after the queued farewell drains.
                await worker.queue_frame(EndFrame())

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, LLMContextFrame):
                recent = next((m for m in reversed(frame.context.messages)
                    if isinstance(m, dict) and m.get("role") == "user"), None)
                if recent and isinstance(recent.get("content"), str):
                    mark = time.monotonic()
                    try:
                        plan = await conversation.turn(recent["content"])
                        await self.speak(plan)
                        emit("voice.turn_prepared", case_id=cid, stage="llm", model=settings.llm_model,
                             duration_ms=round((time.monotonic()-mark)*1000))
                    except Exception as error:
                        emit("voice.turn_failed", case_id=cid, stage="conversation", exception_type=type(error).__name__)
                        await runner.cancel()
                return
            await self.push_frame(frame, direction)

    class SpokenAudit(BaseObserver):
        def __init__(self):
            super().__init__()
            self.parts = []
            self.interrupted = False
            self.first_audio = False
            self.speaking = False

        async def flush(self):
            if not self.parts:
                return
            text = redact(" ".join(self.parts))
            self.parts.clear()
            conversation.heard(text, interrupted=self.interrupted)
            try:
                await conversation.brain.transcript(cid, "out", text)
            except Exception:
                emit("voice.transcript_delivery_failed", case_id=cid)
                await runner.cancel()

        async def on_push_frame(self, data):
            frame = data.frame
            if isinstance(frame, InterruptionFrame) and data.first_push and self.speaking:
                self.interrupted = True
                conversation.heard("", interrupted=True)
            if data.source is not output:
                return
            if isinstance(frame, BotStartedSpeakingFrame):
                self.speaking = True
                if not self.parts:
                    self.interrupted = False
                if not self.first_audio:
                    self.first_audio = True
                    emit("voice.first_audio_sent", case_id=cid, stage="transport",
                         observed_ms=round((time.monotonic()-started)*1000))
            elif isinstance(frame, TTSTextFrame):
                self.parts.append(frame.text)
            elif isinstance(frame, BotStoppedSpeakingFrame):
                self.speaking = False
                await self.flush()

    context = LLMContext()
    aggregators = LLMContextAggregatorPair(context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer(sample_rate=16000),
            user_turn_strategies=UserTurnStrategies(stop=[SpeechTimeoutUserTurnStopStrategy()])))
    dialogue = DialogueProcessor()
    audit = SpokenAudit()
    metrics = ServiceMetricsObserver()

    @metrics.event_handler("on_service_latency")
    async def latency(observer, record):
        emit("voice.service_latency", case_id=cid, kind=record.kind,
             observed_ms=round(record.seconds*1000), model=record.model)

    worker = PipelineWorker(Pipeline([transport.input(), make_stt(settings), RedactionProcessor(),
        aggregators.user(), dialogue, make_tts(settings), output, aggregators.assistant()]),
        enable_rtvi=False, observers=[audit, metrics], processor_unusable_policy=ProcessorUnusablePolicy.CANCEL,
        params=PipelineParams(audio_in_sample_rate=16000, audio_out_sample_rate=8000, enable_metrics=True))
    runner = WorkerRunner(handle_sigint=False)

    @transport.event_handler("on_client_connected")
    async def connected(transport, websocket):
        # The initial plan passed guard checks before the phone was dialed.
        await worker.queue_frames([TTSSpeakFrame(line) for line in initial_plan.lines])

    @transport.event_handler("on_client_disconnected")
    async def disconnected(transport, websocket):
        await runner.cancel()

    @transport.event_handler("on_session_timeout")
    async def timeout(transport, websocket):
        await runner.cancel()

    @worker.event_handler("on_pipeline_error")
    async def pipeline_error(worker, frame):
        emit("voice.pipeline_error", case_id=cid, category=frame.category.value)

    try:
        await runner.add_workers(worker)
        await runner.run()
    finally:
        await audit.flush()
        emit("voice.session_finished", case_id=cid, duration_ms=round((time.monotonic()-started)*1000))


if __name__ == "__main__":
    load_dotenv(Path(__file__).with_name(".env"))
    import logging
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Bind locally. Only the provider webhook/stream routes should be tunnelled.
    uvicorn.run("service:app", host=os.getenv("VOICE_HOST", "127.0.0.1"),
                port=int(os.getenv("VOICE_PORT", "8100")), access_log=False, ws_max_size=16384)
