"""
Endpoint tests for /api/v1/assistant/* (validation, headers, kill switch,
transcribe guards). The engine itself is covered in test_assistant_engine.py.
"""

import io
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas.assistant import AssistantChatResponse

ORG = str(uuid4())
HEADERS = {
    "X-Organization-Id": ORG,
    "X-User-Id": "user-1",
    "X-User-Role": "member",
    "X-Plan": "team",
    "X-Forwarded-Authorization": "Bearer jwt-token",
}
BODY = {"messages": [{"role": "user", "content": "hello"}], "platform": "web"}


class StubEngine:
    def __init__(self, *args, **kwargs):
        pass

    async def run_sync(self):
        return AssistantChatResponse(content="stubbed answer", model="test-model")

    async def run(self):
        yield {"type": "stream_started"}
        yield {"type": "content_chunk", "content": "stubbed"}
        yield {"type": "stream_completed", "content": "stubbed", "citations": [],
               "actions": [], "toolCalls": [], "model": "test-model", "tokenCount": 1}


class TestChatEndpoint:
    def test_missing_identity_headers_400(self, client):
        response = client.post("/api/v1/assistant/chat", json=BODY)
        assert response.status_code == 400

    def test_invalid_org_header_400(self, client):
        headers = {**HEADERS, "X-Organization-Id": "not-a-uuid"}
        response = client.post("/api/v1/assistant/chat", json=BODY, headers=headers)
        assert response.status_code == 400

    def test_last_message_must_be_user_422(self, client):
        body = {"messages": [{"role": "assistant", "content": "hi"}], "platform": "web"}
        response = client.post("/api/v1/assistant/chat", json=body, headers=HEADERS)
        assert response.status_code == 422

    def test_empty_messages_422(self, client):
        response = client.post(
            "/api/v1/assistant/chat", json={"messages": []}, headers=HEADERS
        )
        assert response.status_code == 422

    def test_kill_switch_503(self, client, monkeypatch):
        monkeypatch.setattr(settings, "assistant_enabled", False)
        response = client.post("/api/v1/assistant/chat", json=BODY, headers=HEADERS)
        assert response.status_code == 503

    def test_chat_success(self, client, monkeypatch):
        monkeypatch.setattr(
            "app.api.endpoints.assistant.AssistantEngine", StubEngine
        )
        response = client.post("/api/v1/assistant/chat", json=BODY, headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "stubbed answer"
        assert data["disclaimer"]  # camelCase + fixed disclaimer present

    def test_stream_success_sse_framing(self, client, monkeypatch):
        monkeypatch.setattr(
            "app.api.endpoints.assistant.AssistantEngine", StubEngine
        )
        response = client.post(
            "/api/v1/assistant/chat/stream", json=BODY, headers=HEADERS
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        text = response.text
        assert 'data: {"type": "stream_started"}' in text
        assert text.rstrip().endswith("data: [DONE]")


class TestTranscribeEndpoint:
    def _post(self, client, data: bytes, content_type="audio/webm"):
        return client.post(
            "/api/v1/assistant/transcribe",
            files={"file": ("clip.webm", io.BytesIO(data), content_type)},
            headers=HEADERS,
        )

    def test_unsupported_type_415(self, client):
        response = self._post(client, b"abc", content_type="application/pdf")
        assert response.status_code == 415

    def test_empty_file_400(self, client):
        response = self._post(client, b"")
        assert response.status_code == 400

    def test_too_large_413(self, client, monkeypatch):
        monkeypatch.setattr(settings, "transcribe_max_bytes", 10)
        response = self._post(client, b"x" * 11)
        assert response.status_code == 413

    def test_success(self, client, monkeypatch):
        class StubOpenAI:
            def __init__(self, *args, **kwargs):
                async def create(**kwargs):
                    return SimpleNamespace(text="mera notice dikhao", language="hi", duration=2.5)
                self.audio = SimpleNamespace(
                    transcriptions=SimpleNamespace(create=create)
                )

        monkeypatch.setattr("app.api.endpoints.assistant.AsyncOpenAI", StubOpenAI)
        response = self._post(client, b"fake-audio-bytes")
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "mera notice dikhao"
        assert data["language"] == "hi"
