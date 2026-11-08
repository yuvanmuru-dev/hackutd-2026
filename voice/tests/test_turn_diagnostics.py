"""Speech breadcrumbs contain metadata, never recognized words or decisions."""
import asyncio
import json

from bot import make_user_turn_params
from conversation import Conversation
from test_conversation import ModelStub, setup_case
from turn_diagnostics import TurnDiagnostics


def capture(session):
    events = []
    return TurnDiagnostics(session, lambda event, **fields: events.append({"event": event, **fields})), events


def test_diagnostics_do_not_retain_speech_or_change_approval_state():
    async def run():
        _, request, brain = setup_case()
        session = Conversation(request, brain, ModelStub())
        question = await session.next_action()
        diagnostics, events = capture(session)
        diagnostics.plan_queued(question)
        diagnostics.playback(True)
        diagnostics.recognized("My password is synthetic-private-value and my PIN is 123456", final=True)
        diagnostics.turn_accepted()
        diagnostics.turn_completed()
        diagnostics.question_audited(interrupted=False)
        diagnostics.playback(False)
        logged = json.dumps(events)
        for private in ("password", "synthetic-private-value", "123456", question.lines[-1]):
            assert private not in logged
        assert session.awaiting == question.action_id and not session.heard_question
        assert not session.completed
        brain.decide.assert_not_awaited()
        assert events[3]["gate_reason"] == "question_not_heard"
    asyncio.run(run())


def test_installed_turn_strategy_exposes_dropped_one_word_without_changing_thresholds():
    from pipecat.frames.frames import BotStartedSpeakingFrame, BotStoppedSpeakingFrame, TranscriptionFrame

    async def run():
        _, request, brain = setup_case()
        session = Conversation(request, brain, ModelStub())
        diagnostics, events = capture(session)
        strategy = make_user_turn_params().user_turn_strategies.start[0]

        async def reset(strategy):
            diagnostics.aggregation_reset()

        async def started(strategy, params):
            diagnostics.turn_started()

        strategy.add_event_handler("on_reset_aggregation", reset)
        strategy.add_event_handler("on_user_turn_started", started)
        diagnostics.playback(True)
        await strategy.process_frame(BotStartedSpeakingFrame())
        diagnostics.recognized("yes", final=True, finalized=True)
        await strategy.process_frame(TranscriptionFrame("yes", "maya", "", finalized=True))
        reset_event = next(e for e in events if e["event"] == "voice.turn_aggregation_reset")
        assert reset_event["asr_seq"] == 1 and reset_event["last_asr_word_count"] == 1
        assert reset_event["bot_speaking"] and reset_event["last_asr_final"]
        assert not any(e["event"] == "voice.user_turn_started" for e in events)
        diagnostics.playback(False)
        await strategy.process_frame(BotStoppedSpeakingFrame())
        diagnostics.recognized("yes", final=True, finalized=True)
        await strategy.process_frame(TranscriptionFrame("yes", "maya", "", finalized=True))
        start_event = next(e for e in events if e["event"] == "voice.user_turn_started")
        assert start_event["asr_seq"] == 2 and not start_event["bot_speaking"]
        brain.decide.assert_not_awaited()  # Observing recognition cannot itself approve.
    asyncio.run(run())


def test_late_confirmation_answer_is_visible_as_unarmed_and_never_approves():
    async def run():
        _, request, brain = setup_case()
        session = Conversation(request, brain, ModelStub())
        question = await session.next_action()
        session.heard(question.lines[-1])
        confirmation = await session.turn("are you there?")
        diagnostics, events = capture(session)
        diagnostics.plan_queued(confirmation)
        session.heard("Just to confirm, should I", interrupted=True)
        diagnostics.question_audited(interrupted=True)
        diagnostics.recognized("yes", final=True)
        diagnostics.turn_accepted()
        repeated = await session.turn("yes")
        assert repeated.action_id == question.action_id
        assert events[-1]["gate_reason"] == "question_not_heard"
        brain.decide.assert_not_awaited()
    asyncio.run(run())
