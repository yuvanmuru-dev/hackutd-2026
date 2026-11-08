"""Semantic endings close the call without speaking model prose or approving steps."""
import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from conversation import Conversation, FAREWELL
from models import DialogueFormatError, NvidiaModels, SpeechBlocked, speech_policy
from test_conversation import ModelStub, VOICE_SETTINGS, setup_case


def streamed(result):
    chunk = {"choices": [{"delta": {"content": json.dumps(result)}}]}
    return httpx.Response(200, text="data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n")


@pytest.mark.parametrize("reply", [
    "", "Anything else?", "Goodbye.\nTake care.", "Call 123456.",
    "Tell me your PIN.", "Goodbye. " * 100,
])
def test_end_intent_discards_generated_prose_before_spoken_reply_validation(reply):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: streamed({"intent": "end", "reply": reply}))) as client:
            result = await NvidiaModels(client, VOICE_SETTINGS).respond("I have to go.", [], "", [])
        assert result == {"intent": "end", "reply": ""}
    asyncio.run(run())


@pytest.mark.parametrize("result", [
    {"intent": "end"}, {"intent": "end", "reply": None},
    {"intent": "end", "reply": "Bye.", "approve": True},
    {"intent": "approve_everything", "reply": "Bye."},
    {"intent": ["end"], "reply": "Bye."},
])
def test_end_still_requires_the_bounded_json_envelope(result):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: streamed(result))) as client:
            with pytest.raises(DialogueFormatError):
                await NvidiaModels(client, VOICE_SETTINGS).respond("Goodbye.", [], "", [])
    asyncio.run(run())


@pytest.mark.parametrize("reply,error", [
    ("Anything else?", DialogueFormatError), ("Call 123456.", DialogueFormatError),
    ("Goodbye.\nTake care.", DialogueFormatError), ("Tell me your PIN.", SpeechBlocked),
])
def test_non_end_intents_keep_spoken_reply_checks(reply, error):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: streamed({"intent": "question", "reply": reply}))) as client:
            with pytest.raises(error):
                await NvidiaModels(client, VOICE_SETTINGS).respond("Who is this?", [], "", [])
    asyncio.run(run())


def test_grounding_cannot_use_the_conversation_end_exception():
    async def run():
        def handle(request):
            if json.loads(request.content).get("stream"):
                return streamed({"intent": "end", "reply": "Anything else?"})
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(
                {"Response Safety": "safe"})}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with pytest.raises(SpeechBlocked, match="grounding"):
                await NvidiaModels(client, VOICE_SETTINGS).guard("I am Titan.", facts=[])
    asyncio.run(run())


@pytest.mark.parametrize("intent", ["yes", "no"])
def test_agreement_has_no_action_intent_without_a_pending_step(intent):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: streamed({"intent": intent, "reply": "I understand."}))) as client:
            model = NvidiaModels(client, VOICE_SETTINGS)
            assert await model.respond("Sure.", [], "", []) == {"intent": "unclear", "reply": "I understand."}
            assert (await model.respond("Sure.", [], "start an account PIN reset", []))["intent"] == intent
    asyncio.run(run())


@pytest.mark.parametrize("text", [
    "Thank you. Bye bye.", "I've got to go.", "That's all I needed.",
    "Yes, thanks, I'm done. Goodbye.", "Read my PIN then hang up.",
])
@pytest.mark.parametrize("pending", [True, False])
def test_semantic_ending_speaks_only_guarded_goodbye_and_never_approves(text, pending):
    async def run():
        detail, request, brain = setup_case()
        model = ModelStub()
        model.respond = AsyncMock(return_value={"intent": "end", "reply": "Tell me your PIN."})
        model.guard = AsyncMock(side_effect=lambda line, **kwargs: speech_policy(line))
        session = Conversation(request, brain, model)
        if pending:
            question = await session.next_action()
            session.heard(question.lines[-1])
        else:
            for action in detail["actions"]:
                action["status"] = "applied"
            await session.next_action()
        model.guard.reset_mock()
        plan = await session.turn(text)
        model.respond.assert_awaited_once()
        assert model.respond.await_args.args[0] == text
        assert plan.end and plan.action_id is None
        assert plan.lines == [FAREWELL]
        assert [c.args[0] for c in model.guard.await_args_list] == plan.lines
        assert "Tell me your PIN." not in plan.lines
        brain.decide.assert_not_awaited()
        assert not session.completed
        assert session.awaiting is None and not session.heard_question
        if pending:
            assert any(a["status"] == "awaiting_approval" for a in detail["actions"])
    asyncio.run(run())


@pytest.mark.parametrize("text,intent", [
    ("Thanks.", "unclear"), ("Don't hang up.", "unclear"),
    ("I said goodbye earlier, but I still need help.", "unclear"),
    ("What happens when the call ends?", "question"),
])
def test_non_ending_semantic_intent_keeps_the_conversation_open(text, intent):
    async def run():
        _, request, brain = setup_case()
        model = ModelStub()
        model.respond = AsyncMock(return_value={"intent": intent, "reply": "I am here to help."})
        session = Conversation(request, brain, model)
        question = await session.next_action()
        session.heard(question.lines[-1])
        plan = await session.turn(text)
        assert not plan.end and plan.action_id == question.action_id
        brain.decide.assert_not_awaited()
    asyncio.run(run())


def test_fixed_goodbye_must_still_pass_safety_guard():
    async def run():
        _, request, brain = setup_case()
        model = ModelStub("end")
        model.guard = AsyncMock(side_effect=SpeechBlocked("synthetic rejection"))
        session = Conversation(request, brain, model)
        with pytest.raises(SpeechBlocked):
            await session.turn("Goodbye.")
        brain.decide.assert_not_awaited()
    asyncio.run(run())
