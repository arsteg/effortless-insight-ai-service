"""
Unit tests for the assistant orchestration engine (streaming, tool loop,
action protocol) with a scripted fake OpenAI client — no network calls.
"""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas.assistant import AssistantChatRequest, ChatMessage
from app.services.assistant.context import AssistantContext
from app.services.assistant.engine import AssistantEngine, AssistantError

NOTICE_ID = str(uuid4())


# ---------------------------------------------------------------- fakes --- #

def content_chunk(text):
    return SimpleNamespace(
        usage=None,
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text, tool_calls=None))],
    )


def tool_call_chunks(name, arguments, call_id="call_1"):
    """A tool call split across two deltas, as OpenAI streams them."""
    half = len(arguments) // 2
    return [
        SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(delta=SimpleNamespace(
                content=None,
                tool_calls=[SimpleNamespace(
                    index=0, id=call_id,
                    function=SimpleNamespace(name=name, arguments=arguments[:half]),
                )],
            ))],
        ),
        SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(delta=SimpleNamespace(
                content=None,
                tool_calls=[SimpleNamespace(
                    index=0, id=None,
                    function=SimpleNamespace(name=None, arguments=arguments[half:]),
                )],
            ))],
        ),
    ]


def usage_chunk(total=42):
    return SimpleNamespace(usage=SimpleNamespace(total_tokens=total), choices=[])


class FakeStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class FakeOpenAI:
    """Returns one scripted stream per completions.create call."""

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = []
        completions = SimpleNamespace(create=self._create)
        self.chat = SimpleNamespace(completions=completions)

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.scripts:
            raise AssertionError("FakeOpenAI ran out of scripted responses")
        return FakeStream(self.scripts.pop(0))


class FakeRetriever:
    def __init__(self, blocks=None, citations=None):
        self.blocks = blocks or ["[EI-W07] Invite a CA\nGo to /team ..."]
        self.citations = citations or ["EI-W07"]

    async def retrieve(self, query):
        return self.blocks, self.citations


class FakeExecutor:
    def __init__(self, result=None):
        self.result = result or {"status": "ok", "data": {"total": 5, "overdue": 1}}
        self.calls = []

    async def execute(self, name, args):
        self.calls.append((name, args))
        return self.result


# -------------------------------------------------------------- helpers --- #

def make_engine(scripts, executor=None, token="jwt"):
    ctx = AssistantContext(
        organization_id=uuid4(), user_id="u1", user_role="member",
        plan="team", user_token=token,
    )
    request = AssistantChatRequest(
        messages=[ChatMessage(role="user", content="how do I invite my CA?")],
        platform="web",
    )
    fake = FakeOpenAI(scripts)
    engine = AssistantEngine(
        ctx=ctx, request=request,
        openai_client=fake,
        retriever=FakeRetriever(),
        executor=executor or FakeExecutor(),
    )
    return engine, fake


async def collect(engine):
    return [event async for event in engine.run()]


# ---------------------------------------------------------------- tests --- #

class TestPlainAnswer:
    async def test_streams_content_and_completes(self):
        engine, fake = make_engine([
            [content_chunk("Go to "), content_chunk("Team."), usage_chunk(50)],
        ])
        events = await collect(engine)

        types = [event["type"] for event in events]
        assert types[0] == "stream_started"
        assert types.count("content_chunk") == 2
        completed = events[-1]
        assert completed["type"] == "stream_completed"
        assert completed["content"] == "Go to Team."
        assert completed["citations"] == ["EI-W07"]
        assert completed["tokenCount"] == 50
        assert completed["model"] == settings.assistant_model

    async def test_system_prompt_contains_knowledge_and_role(self):
        engine, fake = make_engine([[content_chunk("ok")]])
        await collect(engine)
        system = fake.calls[0]["messages"][0]
        assert system["role"] == "system"
        assert "EI-W07" in system["content"]
        assert "Role in this organization: member" in system["content"]

    async def test_run_sync_assembles_response(self):
        engine, _ = make_engine([[content_chunk("Hello "), content_chunk("there")]])
        response = await engine.run_sync()
        assert response.content == "Hello there"
        assert response.citations == ["EI-W07"]
        assert response.disclaimer  # fixed disclaimer always present


class TestReadToolLoop:
    async def test_tool_hop_then_answer(self):
        executor = FakeExecutor()
        engine, fake = make_engine(
            [
                tool_call_chunks("get_notice_statistics", "{}"),
                [content_chunk("You have 5 notices, 1 overdue."), usage_chunk(80)],
            ],
            executor=executor,
        )
        events = await collect(engine)

        types = [event["type"] for event in events]
        assert "tool_call_started" in types and "tool_call_completed" in types
        assert executor.calls == [("get_notice_statistics", {})]

        # second LLM call received the tool result wrapped as data
        second_messages = fake.calls[1]["messages"]
        tool_message = [m for m in second_messages if m["role"] == "tool"][0]
        assert "<TOOL_RESULT>" in tool_message["content"]
        assert '"total": 5' in tool_message["content"]

        completed = events[-1]
        assert completed["content"].startswith("You have 5 notices")
        assert completed["toolCalls"][0]["tool"] == "get_notice_statistics"
        assert completed["toolCalls"][0]["status"] == "ok"

    async def test_tool_error_is_surfaced_to_model_not_retried(self):
        executor = FakeExecutor({"status": "error", "code": "FEATURE_NOT_AVAILABLE", "message": "plan"})
        engine, fake = make_engine(
            [
                tool_call_chunks("get_notice_report", json.dumps({"noticeId": NOTICE_ID})),
                [content_chunk("That needs an upgrade.")],
            ],
            executor=executor,
        )
        events = await collect(engine)
        assert len(executor.calls) == 1  # no retry
        completed = events[-1]
        assert completed["toolCalls"][0]["status"] == "error"
        assert completed["toolCalls"][0]["errorCode"] == "FEATURE_NOT_AVAILABLE"

    async def test_no_read_tools_offered_without_user_token(self):
        engine, fake = make_engine([[content_chunk("ok")]], token=None)
        await collect(engine)
        tool_names = {
            spec["function"]["name"] for spec in fake.calls[0].get("tools", [])
        }
        assert "get_notices" not in tool_names
        assert {"suggest_navigation", "propose_action"} <= tool_names


class TestActions:
    async def test_navigation_action_emitted(self):
        engine, _ = make_engine([
            tool_call_chunks("suggest_navigation", json.dumps({"intent": "team"})),
            [content_chunk("Open the Team page and click Invite member.")],
        ])
        events = await collect(engine)
        action_events = [event for event in events if event["type"] == "action"]
        assert len(action_events) == 1
        action = action_events[0]["action"]
        assert action["type"] == "navigate"
        assert action["webRoute"] == "/team"
        assert "_fresh" not in action

    async def test_unknown_intent_produces_no_action(self):
        engine, fake = make_engine([
            tool_call_chunks("suggest_navigation", json.dumps({"intent": "admin_portal"})),
            [content_chunk("I cannot open that.")],
        ])
        events = await collect(engine)
        assert not [event for event in events if event["type"] == "action"]
        tool_message = [m for m in fake.calls[1]["messages"] if m["role"] == "tool"][0]
        assert "UNKNOWN_INTENT" in tool_message["content"]

    async def test_proposal_emits_confirm_card_and_never_executes(self):
        executor = FakeExecutor()
        engine, _ = make_engine(
            [
                tool_call_chunks("propose_action", json.dumps({
                    "kind": "create_task",
                    "summary": "Create task 'Reply to DRC-01' on the notice",
                    "params": {"noticeId": NOTICE_ID, "title": "Reply to DRC-01"},
                })),
                [content_chunk("Ready — confirm to create the task.")],
            ],
            executor=executor,
        )
        events = await collect(engine)
        action = [event for event in events if event["type"] == "action"][0]["action"]
        assert action["type"] == "confirm_action"
        assert action["kind"] == "create_task"
        assert action["path"] == "/api/v1/tasks"
        assert executor.calls == []  # the AI service never executed anything

    async def test_invalid_proposal_rejected(self):
        engine, fake = make_engine([
            tool_call_chunks("propose_action", json.dumps({
                "kind": "delete_notice", "summary": "del", "params": {},
            })),
            [content_chunk("I can't do that, but here's how you can.")],
        ])
        events = await collect(engine)
        assert not [event for event in events if event["type"] == "action"]
        tool_message = [m for m in fake.calls[1]["messages"] if m["role"] == "tool"][0]
        assert "INVALID_ACTION" in tool_message["content"]


class TestLoopBounds:
    async def test_final_hop_forces_answer_without_tools(self):
        hops = settings.assistant_max_tool_hops
        scripts = [
            tool_call_chunks("get_notice_statistics", "{}", call_id=f"call_{i}")
            for i in range(hops)
        ]
        scripts.append([content_chunk("Final answer.")])
        engine, fake = make_engine(scripts)
        events = await collect(engine)

        assert events[-1]["content"] == "Final answer."
        assert len(fake.calls) == hops + 1
        assert "tools" in fake.calls[0]
        assert "tools" not in fake.calls[-1]  # forced answer, no tools offered


class TestFailure:
    async def test_llm_error_yields_error_event(self):
        from openai import OpenAIError

        class BrokenOpenAI:
            def __init__(self):
                async def create(**kwargs):
                    raise OpenAIError("boom")
                self.chat = SimpleNamespace(
                    completions=SimpleNamespace(create=create)
                )

        ctx = AssistantContext(organization_id=uuid4(), user_id="u1", user_token="t")
        request = AssistantChatRequest(
            messages=[ChatMessage(role="user", content="hi")], platform="web"
        )
        engine = AssistantEngine(
            ctx=ctx, request=request,
            openai_client=BrokenOpenAI(),
            retriever=FakeRetriever(), executor=FakeExecutor(),
        )
        events = [event async for event in engine.run()]
        assert events[-1]["type"] == "error"

        with pytest.raises(AssistantError):
            await AssistantEngine(
                ctx=ctx, request=request,
                openai_client=BrokenOpenAI(),
                retriever=FakeRetriever(), executor=FakeExecutor(),
            ).run_sync()
