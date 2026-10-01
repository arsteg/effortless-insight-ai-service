"""
Regression tests for openai SDK compatibility (pinned 1.12 lacks
stream_options) and for the engine's never-500 error contract.
"""

from types import SimpleNamespace
from uuid import uuid4

from app.schemas.assistant import AssistantChatRequest, ChatMessage
from app.services.assistant import engine as engine_module
from app.services.assistant.context import AssistantContext
from app.services.assistant.engine import AssistantEngine


def content_chunk(text):
    return SimpleNamespace(
        usage=None,
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text, tool_calls=None))],
    )


class LegacyStream:
    """Chunks WITHOUT a usage attribute, like older SDK models."""

    def __init__(self, texts):
        self._chunks = [
            SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=t, tool_calls=None))]
            )
            for t in texts
        ]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class LegacyOpenAI:
    """Rejects stream_options with TypeError, like openai<1.26."""

    def __init__(self):
        self.calls = []

        async def create(**kwargs):
            self.calls.append(kwargs)
            if "stream_options" in kwargs:
                raise TypeError(
                    "AsyncCompletions.create() got an unexpected keyword argument 'stream_options'"
                )
            return LegacyStream(["Hello ", "there"])

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


class FakeRetriever:
    async def retrieve(self, query):
        return [], []


class CrashingRetrieverEngineOpenAI:
    def __init__(self):
        async def create(**kwargs):
            raise RuntimeError("totally unexpected")

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


def make_engine(client):
    ctx = AssistantContext(organization_id=uuid4(), user_id="u1", user_token="t")
    request = AssistantChatRequest(
        messages=[ChatMessage(role="user", content="hi")], platform="web"
    )
    return AssistantEngine(
        ctx=ctx, request=request, openai_client=client, retriever=FakeRetriever()
    )


class TestLegacySdkCompat:
    async def test_retries_without_stream_options_and_answers(self):
        engine_module._STREAM_OPTIONS_SUPPORTED = None  # reset feature flag
        client = LegacyOpenAI()
        engine = make_engine(client)

        response = await engine.run_sync()

        assert response.content == "Hello there"
        assert response.token_count == 0  # usage unavailable on legacy SDK
        # first call tried stream_options, second succeeded without it
        assert "stream_options" in client.calls[0]
        assert "stream_options" not in client.calls[1]

    async def test_feature_flag_caches_lack_of_support(self):
        engine_module._STREAM_OPTIONS_SUPPORTED = None
        client = LegacyOpenAI()
        await make_engine(client).run_sync()
        calls_after_first = len(client.calls)

        await make_engine(client).run_sync()
        # second turn must not re-attempt stream_options
        assert "stream_options" not in client.calls[-1]
        assert len(client.calls) == calls_after_first + 1


class TestNever500Contract:
    async def test_unexpected_exception_becomes_error_event(self):
        engine = make_engine(CrashingRetrieverEngineOpenAI())
        events = [event async for event in engine.run()]
        assert events[-1]["type"] == "error"
        assert events[-1]["message"] == "assistant_unavailable"
