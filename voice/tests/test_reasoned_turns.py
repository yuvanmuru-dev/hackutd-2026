import asyncio
import json
from dataclasses import replace
from unittest.mock import AsyncMock

import httpx
import pytest

from conversation import Conversation
from models import DialogueFormatError, NvidiaModels, SpeechBlocked
from test_conversation import ModelStub, VOICE_SETTINGS, setup_case


@pytest.mark.parametrize("text,intent,reply,approved", [
    ("yeah sure", "yes", "I understand.", True),
    ("who is this?", "question", "I am Titan, your account-security assistant.", False),
    ("read me my PIN", "secret", "I will never read back your PIN. Keep it private.", False),
    ("maybe later", "unclear", "I understand.", False),
])
def test_contextual_turn_has_one_bounded_approval(text, intent, reply, approved):
    async def run():
        _, request, brain = setup_case()
        model = ModelStub()
        model.respond = AsyncMock(return_value={"intent": intent, "reply": reply})
        session = Conversation(request, brain, model)
        question = await session.next_action()
        session.heard(question.lines[-1])
        plan = await session.turn(text)
        args = model.respond.await_args.args
        assert args[1] == request["facts"] and args[2] == "start an account PIN reset"
        if approved:
            brain.decide.assert_awaited_once_with(question.action_id, True)
            assert plan.action_id != question.action_id
            assert "That step is complete." in plan.lines
            await session.turn("yes")
            assert brain.decide.await_count == 1
        else:
            brain.decide.assert_not_awaited()
            assert plan.action_id == question.action_id
            assert reply in plan.lines if intent != "unclear" else plan.lines[-1].startswith("Just to confirm,")
    asyncio.run(run())


@pytest.mark.parametrize("failure", [httpx.ConnectError("synthetic model down"), SpeechBlocked("synthetic guard rejection")])
def test_model_or_reply_guard_failure_uses_template_without_approval(failure):
    async def run():
        _, request, brain = setup_case()
        model = ModelStub()
        model.respond = AsyncMock(side_effect=failure)
        session = Conversation(request, brain, model)
        question = await session.next_action()
        session.heard(question.lines[-1])
        plan = await session.turn("yeah sure")
        assert plan.lines[-1].startswith("Just to confirm,")
        brain.decide.assert_not_awaited()
    asyncio.run(run())


def test_model_yes_cannot_approve_unheard_or_looser_question():
    async def run():
        detail, request, brain = setup_case()
        model = ModelStub()
        model.respond = AsyncMock(return_value={"intent": "yes", "reply": "I understand."})
        session = Conversation(request, brain, model)
        question = await session.next_action()
        await session.turn("yeah sure")
        brain.decide.assert_not_awaited()
        action = next(a for a in detail["actions"] if a["action_id"] == question.action_id)
        action.update(direction="looser", kind="release_hold")
        plan = await session.next_action()
        session.heard(plan.lines[-1])
        await session.turn("yes")
        brain.decide.assert_not_awaited()
    asyncio.run(run())


def test_brev_failure_uses_lightning_with_bounded_redacted_context():
    async def run():
        seen = []
        def handle(request):
            seen.append(request)
            if request.url.host == "brev.example.invalid": return httpx.Response(503)
            body = json.loads(request.content)
            assert body["chat_template_kwargs"] == {"enable_thinking": False}
            ctx = json.loads(body["messages"][1]["content"])
            assert len(ctx["history"]) == 8 and "123456" not in json.dumps(ctx)
            reply = {"intent": "question", "reply": "I am Titan, your account-security assistant."}
            chunk = {"choices": [{"delta": {"reasoning_content": "private thoughts", "content": json.dumps(reply)}}]}
            return httpx.Response(200, text="data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n")
        settings = replace(VOICE_SETTINGS, nano_base_url="https://brev.example.invalid/v1", nano_model="nvidia/synthetic-nano")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            result = await NvidiaModels(client, settings).respond("who is this 123456", ["Protection is on."],
                "start an account PIN reset", [{"role": "user", "content": "123456"}] * 12)
        assert result["intent"] == "question"
        assert len(seen) == 2 and seen[1].url.host == "integrate.api.nvidia.com"
    asyncio.run(run())


def test_unsupported_generated_fact_is_rejected_by_grounding_guard():
    async def run():
        def handle(request):
            body = json.loads(request.content)
            if body.get("stream"):
                chunk = {"choices": [{"delta": {"content": json.dumps({"intent": "no", "reply": "Unsupported."})}}]}
                return httpx.Response(200, text="data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n")
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(
                {"Response Safety": "safe", "Response Grounding": "unsupported"})}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with pytest.raises(SpeechBlocked):
                await NvidiaModels(client, VOICE_SETTINGS).guard("Your transfer is cancelled.", facts=["Protection is on."])
    asyncio.run(run())


def test_setup_probe_instructs_model_to_leave_questions_to_the_application():
    async def run():
        def handle(request):
            body = json.loads(request.content)
            instruction = body["messages"][0]["content"]
            assert "Do not ask any questions or use question marks" in instruction
            result = {"intent": "question", "reply": "I am Titan, your account-security assistant."}
            chunk = {"choices": [{"delta": {"content": json.dumps(result)}}]}
            return httpx.Response(200, text="data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            await NvidiaModels(client, VOICE_SETTINGS).verify()
    asyncio.run(run())


def test_model_question_does_not_bypass_the_single_question_guard():
    async def run():
        def handle(request):
            result = {"intent": "question", "reply": "How can I help protect your account today?"}
            chunk = {"choices": [{"delta": {"content": json.dumps(result)}}]}
            return httpx.Response(200, text="data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with pytest.raises(DialogueFormatError, match="Invalid bounded conversation response"):
                await NvidiaModels(client, VOICE_SETTINGS).respond("I need help.", [], "", [])
    asyncio.run(run())


@pytest.mark.parametrize("reply", [
    json.dumps({"intent": "question", "reply": "How can I help protect your account today?"}),
    "not JSON",
])
def test_warmup_format_slip_does_not_abort_setup(reply):
    async def run():
        def handle(request):
            chunk = {"choices": [{"delta": {"content": reply}}]}
            return httpx.Response(200, text="data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            await NvidiaModels(client, VOICE_SETTINGS).verify()
    asyncio.run(run())


@pytest.mark.parametrize("failure", [httpx.ConnectError("synthetic unavailable"), SpeechBlocked("synthetic unsafe")])
def test_warmup_does_not_hide_endpoint_or_speech_policy_failures(failure):
    async def run():
        async with httpx.AsyncClient() as client:
            model = NvidiaModels(client, VOICE_SETTINGS)
            model.respond = AsyncMock(side_effect=failure)
            with pytest.raises(type(failure)):
                await model.verify()
    asyncio.run(run())
