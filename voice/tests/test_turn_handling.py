"""Exercise installed Pipecat turn detection without hosted speech or phone calls."""
import asyncio
from array import array
from unittest.mock import AsyncMock

from bot import make_user_turn_params
from pipecat.audio.vad.vad_analyzer import VADState
from pipecat.frames.frames import (
    BotStartedSpeakingFrame, BotStoppedSpeakingFrame, InterimTranscriptionFrame,
    TranscriptionFrame, VADUserStartedSpeakingFrame, VADUserStoppedSpeakingFrame,
)


def test_noise_and_one_word_backchannel_do_not_interrupt_playback():
    async def run():
        strategy = make_user_turn_params().user_turn_strategies.start[0]
        started, discarded = AsyncMock(), AsyncMock()
        strategy.add_event_handler("on_user_turn_started", started)
        strategy.add_event_handler("on_reset_aggregation", discarded)
        await strategy.process_frame(BotStartedSpeakingFrame())
        await strategy.process_frame(VADUserStartedSpeakingFrame())
        await strategy.process_frame(VADUserStoppedSpeakingFrame())
        await strategy.process_frame(InterimTranscriptionFrame("um", "maya", ""))
        await strategy.process_frame(TranscriptionFrame("yes", "maya", "", finalized=True))
        started.assert_not_awaited()
        assert discarded.await_count == 2
    asyncio.run(run())


def test_recognized_phrase_can_barge_in_and_single_answer_works_after_playback():
    async def run():
        strategy = make_user_turn_params().user_turn_strategies.start[0]
        started = AsyncMock()
        strategy.add_event_handler("on_user_turn_started", started)
        await strategy.process_frame(BotStartedSpeakingFrame())
        await strategy.process_frame(InterimTranscriptionFrame("please stop", "maya", ""))
        started.assert_awaited_once()
        assert started.await_args.args[-1].enable_interruptions
        await strategy.handle_user_turn_started()
        await strategy.process_frame(BotStoppedSpeakingFrame())
        await strategy.process_frame(TranscriptionFrame("yes", "maya", "", finalized=True))
        assert started.await_count == 2
    asyncio.run(run())


def test_silero_rejects_synthetic_quiet_noise_and_brief_click():
    async def run():
        vad = make_user_turn_params().vad_analyzer
        vad.set_sample_rate(16000)
        # Deterministic low-level non-speech and a single loud sample, never
        # captured audio. Feed complete Silero windows through the real model.
        states = []
        try:
            for index in range(40):
                samples = array("h", (100 if (i + index) % 2 else -100 for i in range(512)))
                if index == 15:
                    samples[100] = 30000
                states.append(await vad.analyze_audio(samples.tobytes()))
            assert VADState.SPEAKING not in states
        finally:
            await vad.cleanup()
    asyncio.run(run())
