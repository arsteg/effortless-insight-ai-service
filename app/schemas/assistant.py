"""
Request/response schemas for the in-app assistant.

Serialization is camelCase (CamelCaseModel) for .NET/web/mobile interop.
The .NET gateway owns conversation persistence; each request carries the
recent message window plus client context. User identity/org/plan arrive
as headers set by the gateway (see app/services/assistant/context.py).
"""

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.responses import AI_DISCLAIMER, CamelCaseModel


class ChatMessage(BaseModel):
    """One message of the conversation window sent by the gateway."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=8000)


class ClientContext(BaseModel):
    """Where the user currently is in the app (optional grounding)."""

    route: Optional[str] = Field(None, max_length=300)
    notice_id: Optional[UUID] = Field(None, alias="noticeId")

    class Config:
        populate_by_name = True


class AssistantChatRequest(BaseModel):
    """Chat turn request (sync and streaming share this shape)."""

    messages: List[ChatMessage] = Field(..., min_length=1)
    platform: Literal["web", "mobile"] = "web"
    context: Optional[ClientContext] = None

    class Config:
        populate_by_name = True

    @field_validator("messages")
    @classmethod
    def last_message_is_user(cls, v: List[ChatMessage]) -> List[ChatMessage]:
        if v[-1].role != "user":
            raise ValueError("last message must be from the user")
        return v


class NavigateAction(CamelCaseModel):
    """Tells the client to offer a navigation button."""

    type: Literal["navigate"] = "navigate"
    intent: str
    label: str
    web_route: Optional[str] = None
    mobile_route: Optional[str] = None
    web_only_note: Optional[str] = None


class ConfirmAction(CamelCaseModel):
    """
    A proposed write the CLIENT may execute after explicit user confirmation.
    The AI service never executes these.
    """

    type: Literal["confirm_action"] = "confirm_action"
    kind: str
    summary: str
    method: Literal["POST", "PUT"]
    path: str
    body: Dict[str, Any] = Field(default_factory=dict)


class ToolCallInfo(CamelCaseModel):
    """Audit info about a read-tool call made during the turn."""

    tool: str
    status: Literal["ok", "error"]
    error_code: Optional[str] = None


class AssistantChatResponse(CamelCaseModel):
    """Non-streaming chat response."""

    content: str
    citations: List[str] = Field(default_factory=list)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    tool_calls: List[ToolCallInfo] = Field(default_factory=list)
    model: str = ""
    token_count: int = 0
    disclaimer: str = Field(default=AI_DISCLAIMER)


class TranscribeResponse(CamelCaseModel):
    """Speech-to-text result."""

    text: str
    language: Optional[str] = None
    duration_seconds: Optional[float] = None
