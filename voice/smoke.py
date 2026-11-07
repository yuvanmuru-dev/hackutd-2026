"""Preflight for the bridge milestone; never initiates a telephone call."""
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


async def synthesize(settings: Settings) -> int:
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

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, OutputAudioRawFrame):
                self.byte_count += len(frame.audio)
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
            await worker.queue_frames([TTSSpeakFrame(GREETING), EndFrame()])
            await runner.add_workers(worker)
            await runner.run()
    finally:
        if not worker.has_finished():
            await runner.cancel()
    if errors or check.byte_count == 0:
        raise ValueError("Configured Pipecat TTS factory did not synthesize audio")
    return check.byte_count


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
    args = parser.parse_args()
    load_dotenv(Path(__file__).with_name(".env"))
    try:
        asyncio.run(offline() if args.offline else live())
    except Exception as error:
        # Error messages from provider SDKs can contain tokens, URLs, or bodies.
        print(f"SMOKE FAILED: {type(error).__name__}; inspect configuration/provider diagnostics privately")
        raise SystemExit(1) from None
