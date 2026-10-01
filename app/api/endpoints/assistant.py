"""
In-app assistant endpoints.

Called ONLY by the .NET gateway (shared X-API-Key middleware), which
authenticates the end user and forwards identity headers — see
app/services/assistant/context.py. Transports:
- POST /assistant/chat         : non-streaming turn (mobile-friendly)
- POST /assistant/chat/stream  : SSE streaming turn (web)
- POST /assistant/transcribe   : speech-to-text for voice input
"""

import json

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI, OpenAIError

from app.core.config import settings
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    TranscribeResponse,
)
from app.services.assistant.context import AssistantContext, get_assistant_context
from app.services.assistant.engine import AssistantEngine, AssistantError

router = APIRouter()
logger = structlog.get_logger()

ALLOWED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp4", "audio/m4a", "audio/x-m4a",
    "audio/wav", "audio/x-wav", "audio/webm", "audio/ogg", "video/webm",
}


def _require_enabled() -> None:
    if not settings.assistant_enabled:
        raise HTTPException(status_code=503, detail="Assistant is disabled")


@router.post("/chat", response_model=AssistantChatResponse)
async def chat(
    request: AssistantChatRequest,
    ctx: AssistantContext = Depends(get_assistant_context),
) -> AssistantChatResponse:
    """Non-streaming chat turn (used by mobile and as the simple fallback)."""
    _require_enabled()
    engine = AssistantEngine(ctx=ctx, request=request)
    try:
        return await engine.run_sync()
    except AssistantError:
        raise HTTPException(status_code=502, detail="Assistant is temporarily unavailable")


@router.post("/chat/stream")
async def chat_stream(
    request: AssistantChatRequest,
    ctx: AssistantContext = Depends(get_assistant_context),
) -> StreamingResponse:
    """SSE streaming chat turn (used by the web app via the gateway)."""
    _require_enabled()
    engine = AssistantEngine(ctx=ctx, request=request)

    async def event_source():
        try:
            async for event in engine.run():
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        except Exception as exc:  # never leak an unterminated stream
            logger.error("Assistant stream crashed", error=type(exc).__name__)
            yield f"data: {json.dumps({'type': 'error', 'message': 'assistant_unavailable'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    file: UploadFile = File(...),
    ctx: AssistantContext = Depends(get_assistant_context),
) -> TranscribeResponse:
    """Speech-to-text for assistant voice input (English/Hindi auto-detected)."""
    _require_enabled()

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported audio type: {content_type}")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(data) > settings.transcribe_max_bytes:
        raise HTTPException(status_code=413, detail="Audio file too large")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        result = await client.audio.transcriptions.create(
            model=settings.transcribe_model,
            file=(file.filename or "audio.webm", data, content_type),
        )
    except OpenAIError as exc:
        logger.error("Transcription failed", error=type(exc).__name__)
        raise HTTPException(status_code=502, detail="Transcription is temporarily unavailable")

    return TranscribeResponse(
        text=result.text or "",
        language=getattr(result, "language", None),
        duration_seconds=getattr(result, "duration", None),
    )
