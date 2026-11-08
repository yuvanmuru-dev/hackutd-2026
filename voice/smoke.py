"""Bridge and conversation provider checks; never initiates a telephone call."""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import inspect
import json
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
import httpx

from brain import Brain, validate
from config import Settings


async def offline() -> None:
    from loguru import logger
    logger.remove()
    from bot import make_tts
    for provider in ["elevenlabs", "magpie"]:
        settings = Settings(tts_provider=provider, elevenlabs_key="synthetic", elevenlabs_voice="synthetic",
                            nvidia_key="synthetic", magpie_voice="synthetic")
        service = make_tts(settings)
        print(f"OFFLINE: {provider} factory constructed {type(service).__name__}; no provider contacted")
    fixtures = Path(__file__).resolve().parents[1] / "contracts/fixtures"
    for filename, name in [("callreq.t2.json", "CallRequest"), ("event.call_started.json", "Event")]:
        validate(name, json.loads((fixtures / filename).read_text(encoding="utf-8")))
    print(f"OFFLINE PASS: shared fixtures valid; pipecat-ai={importlib.metadata.version('pipecat-ai')}")


async def discover_voice(settings: Settings) -> None:
    if settings.tts_provider == "elevenlabs":
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get("https://api.elevenlabs.io/v1/voices/" + quote(settings.elevenlabs_voice, safe=""),
                                        headers={"xi-api-key": settings.elevenlabs_key})
            response.raise_for_status()
            if response.json().get("voice_id") != settings.elevenlabs_voice:
                raise ValueError("Selected ElevenLabs voice was not returned by voice discovery")
    else:
        # Use the same published model/function map as the pinned Pipecat factory.
        import riva.client
        from riva.client.proto import riva_tts_pb2 as rtts
        from google.protobuf.json_format import MessageToDict
        from pipecat.services.nvidia.tts import NvidiaTTSService
        model = inspect.signature(NvidiaTTSService).parameters["model_function_map"].default
        auth = riva.client.Auth(None, True, "grpc.nvcf.nvidia.com:443",
                                [["function-id", model["function_id"]], ["authorization", "Bearer " + settings.nvidia_key]])
        try:
            synthesis = riva.client.SpeechSynthesisService(auth)
            config = await asyncio.to_thread(synthesis.stub.GetRivaSynthesisConfig,
                                             rtts.RivaSynthesisConfigRequest(), timeout=15)
            def values(obj):
                if isinstance(obj, dict):
                    for value in obj.values():
                        yield from values(value)
                elif isinstance(obj, list):
                    for value in obj:
                        yield from values(value)
                elif isinstance(obj, str):
                    yield from (v.strip() for v in obj.split(","))
            returned = set(values(MessageToDict(config)))
            if settings.magpie_voice not in returned:
                raise ValueError("Selected Magpie voice was not returned by synthesis configuration")
        finally:
            auth.channel.close()
    print("LIVE: selected TTS voice returned by provider discovery")


async def synthesize(settings: Settings, text: str | None = None, *, retain_audio: bool = False) -> int | bytes:
    from loguru import logger
    logger.remove()
    from bot import GREETING, make_tts
    from pipecat.frames.frames import EndFrame, OutputAudioRawFrame, TTSSpeakFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.workers.runner import WorkerRunner

    class AudioCheck(FrameProcessor):
        def __init__(self):
            super().__init__()
            self.byte_count = 0
            self.audio = bytearray()

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, OutputAudioRawFrame):
                self.byte_count += len(frame.audio)
                if retain_audio:
                    self.audio.extend(frame.audio)
            await self.push_frame(frame, direction)

    check = AudioCheck()
    worker = PipelineWorker(Pipeline([make_tts(settings), check]), enable_rtvi=False,
                            processor_unusable_policy=ProcessorUnusablePolicy.CANCEL,
                            params=PipelineParams(audio_out_sample_rate=8000))
    runner = WorkerRunner(handle_sigint=False)
    errors = []

    @worker.event_handler("on_pipeline_error")
    async def failed(worker, frame):
        errors.append(str(frame.category))

    try:
        async with asyncio.timeout(40):
            await worker.queue_frames([TTSSpeakFrame(text or GREETING), EndFrame()])
            await runner.add_workers(worker)
            await runner.run()
    finally:
        if not worker.has_finished():
            await runner.cancel()
    if errors or check.byte_count == 0:
        raise ValueError("Configured Pipecat TTS factory did not synthesize audio")
    return bytes(check.audio) if retain_audio else check.byte_count


async def conversation_check() -> None:
    """Synthetic spoken input → hosted ASR → Lightning intent → guarded spoken reply."""
    import audioop
    import riva.client
    from riva.client.asr import streaming_request_generator
    from models import ASR_FUNCTION_ID, NvidiaModels, verify_asr
    settings = Settings.from_env()
    missing = settings.conversation_missing()
    if missing:
        print("CONVERSATION BLOCKED: " + ", ".join(missing))
        raise SystemExit(1)
    await discover_voice(settings)
    await verify_asr(settings)
    audio = await synthesize(settings, "I need help protecting my account.", retain_audio=True)
    pcm, _ = audioop.ratecv(audio, 2, 1, 8000, 16000, None)
    pcm += b"\x00" * 32000
    def recognize():
        auth = riva.client.Auth(None, True, "grpc.nvcf.nvidia.com:443",
            [["function-id", ASR_FUNCTION_ID], ["authorization", "Bearer " + settings.nvidia_key]])
        try:
            service = riva.client.ASRService(auth)
            config = riva.client.StreamingRecognitionConfig(config=riva.client.RecognitionConfig(
                encoding=riva.client.AudioEncoding.LINEAR_PCM, language_code="en-US",
                sample_rate_hertz=16000, audio_channel_count=1, enable_automatic_punctuation=True),
                interim_results=False)
            chunks = (pcm[i:i+3200] for i in range(0, len(pcm), 3200))
            responses = service.stub.StreamingRecognize(streaming_request_generator(chunks, config), timeout=20)
            return " ".join(result.alternatives[0].transcript for response in responses
                for result in response.results if result.is_final and result.alternatives)
        finally:
            auth.channel.close()
    transcript = await asyncio.to_thread(recognize)
    if "help" not in transcript.lower() or "account" not in transcript.lower():
        raise ValueError("Hosted ASR did not recognize the synthetic help request")
    async with httpx.AsyncClient(timeout=25) as client:
        models = NvidiaModels(client, settings)
        if await models.intent(transcript) != "help":
            raise ValueError("Lightning did not interpret the spoken help request")
        reply = await models.guard("I can help. I will never ask for your PIN or a code.")
    byte_count = await synthesize(settings, reply)
    print(f"CONVERSATION PROVIDERS PASS: synthetic speech recognized, Lightning intent validated, Safety Guard passed, {byte_count} reply PCM bytes")
    print("PHONE EXCHANGE STILL UNVERIFIED: this in-memory check does not test Twilio transport or listener latency")


async def live() -> None:
    settings = Settings.from_env()
    missing = settings.missing(forwarding=True, speech=True)
    if missing:
        # Names and validation descriptions only, never values.
        print("LIVE BLOCKED: " + ", ".join(missing))
        raise SystemExit(1)
    async with httpx.AsyncClient(base_url=settings.brain_url, timeout=8) as client:
        await Brain(client).health()
    print("LIVE: brain health OK")
    await discover_voice(settings)
    byte_count = await synthesize(settings)
    print(f"LIVE TTS PASS: {byte_count} PCM bytes synthesized in memory; no audio file saved")
    print("SIP BRIDGE STILL UNVERIFIED: place the allowlisted probe call and confirm the greeting on the phone")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--offline", action="store_true")
    group.add_argument("--live", action="store_true")
    group.add_argument("--conversation", action="store_true")
    args = parser.parse_args()
    load_dotenv(Path(__file__).with_name(".env"))
    try:
        asyncio.run(offline() if args.offline else conversation_check() if args.conversation else live())
    except Exception as error:
        # Error messages from provider SDKs can contain tokens, URLs, or bodies.
        print(f"SMOKE FAILED: {type(error).__name__}; inspect configuration/provider diagnostics privately")
        raise SystemExit(1) from None
