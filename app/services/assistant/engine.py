"""
Assistant orchestration engine.

A single async event-generator drives both transports:
- the SSE endpoint forwards events as they are yielded;
- the sync endpoint drains the generator and assembles one response.

Event protocol (superset of the web app's existing ai-chat SSE contract):
  stream_started | content_chunk | tool_call_started | tool_call_completed |
  action | stream_completed | error
"""

import json
from typing import Any, AsyncIterator, Dict, List, Optional

import structlog
from openai import AsyncOpenAI

from app.core.config import settings
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    ToolCallInfo,
)
from app.services.assistant.context import AssistantContext
from app.services.assistant.prompts import build_system_prompt
from app.services.assistant.retrieval import ProductKnowledgeRetriever
from app.services.assistant import tools as tool_registry
from app.services.assistant.tools import (
    ToolExecutor,
    ToolValidationError,
    build_confirm_action,
    openai_tool_specs,
    resolve_navigation,
    shrink_result,
)
from app.services.security.prompt_sanitizer import sanitize_user_input

logger = structlog.get_logger()

# Structural sentinels used in our prompts; user text must never contain them
# so it cannot fake a knowledge block or a tool result.
_SENTINELS = ("<PRODUCT_KNOWLEDGE>", "</PRODUCT_KNOWLEDGE>", "<TOOL_RESULT>", "</TOOL_RESULT>")


def neutralize_sentinels(text: str) -> str:
    """Strip prompt-structure sentinel tags from untrusted text."""
    for sentinel in _SENTINELS:
        text = text.replace(sentinel, "")
    return text


class AssistantError(Exception):
    """Fatal error for this turn (LLM unavailable etc.)."""


# openai<1.26 does not accept stream_options (usage reporting on streams).
# Feature-detected at runtime so the assistant works on the pinned 1.12 SDK;
# without it, per-turn tokenCount is 0 (cost still bounded by rate limits).
_STREAM_OPTIONS_SUPPORTED: Optional[bool] = None


class AssistantEngine:
    def __init__(
        self,
        ctx: AssistantContext,
        request: AssistantChatRequest,
        openai_client: Optional[AsyncOpenAI] = None,
        retriever: Optional[ProductKnowledgeRetriever] = None,
        executor: Optional[ToolExecutor] = None,
    ) -> None:
        self._ctx = ctx
        self._request = request
        self._openai = openai_client or AsyncOpenAI(api_key=settings.openai_api_key)
        self._retriever = retriever or ProductKnowledgeRetriever()
        self._executor = executor or ToolExecutor(ctx)
        self._actions: List[Dict[str, Any]] = []
        self._tool_calls: List[ToolCallInfo] = []
        self._citations: List[str] = []
        self._token_count = 0

    async def run(self) -> AsyncIterator[Dict[str, Any]]:
        """Yield protocol events for one chat turn."""
        yield {"type": "stream_started"}

        try:
            messages = await self._build_messages()
        except Exception as exc:  # retrieval/prompt failures degrade, not crash
            logger.error("Assistant prompt build failed", error=str(exc))
            yield {"type": "error", "message": "assistant_unavailable"}
            return

        final_content = ""
        tools_enabled = True

        try:
            for hop in range(settings.assistant_max_tool_hops + 1):
                # Last allowed hop: force an answer, no more tool calls.
                allow_tools = tools_enabled and hop < settings.assistant_max_tool_hops

                content, tool_calls = None, None
                async for event in self._one_completion(messages, allow_tools):
                    if event["type"] == "_final":
                        content, tool_calls = event["content"], event["tool_calls"]
                    else:
                        yield event

                if not tool_calls:
                    final_content = content or ""
                    break

                messages.append({
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": call["arguments"],
                            },
                        }
                        for call in tool_calls
                    ],
                })

                for call in tool_calls:
                    async for event in self._dispatch_tool(call, messages):
                        yield event

        except Exception as exc:  # any turn failure must end as a clean error event, never a 500
            logger.error(
                "Assistant LLM call failed",
                error=type(exc).__name__,
                detail=str(exc)[:200],
            )
            yield {"type": "error", "message": "assistant_unavailable"}
            return

        yield {
            "type": "stream_completed",
            "content": final_content,
            "citations": self._citations,
            "actions": self._actions,
            "toolCalls": [info.model_dump(by_alias=True) for info in self._tool_calls],
            "model": settings.assistant_model,
            "tokenCount": self._token_count,
        }

    async def run_sync(self) -> AssistantChatResponse:
        """Drain the event stream into a single non-streaming response."""
        content_parts: List[str] = []
        completed: Optional[Dict[str, Any]] = None

        async for event in self.run():
            if event["type"] == "content_chunk":
                content_parts.append(event["content"])
            elif event["type"] == "stream_completed":
                completed = event
            elif event["type"] == "error":
                raise AssistantError(event["message"])

        if completed is None:
            raise AssistantError("assistant_unavailable")

        return AssistantChatResponse(
            content=completed["content"] or "".join(content_parts),
            citations=completed["citations"],
            actions=completed["actions"],
            tool_calls=self._tool_calls,
            model=completed["model"],
            token_count=completed["tokenCount"],
        )

    # ------------------------------------------------------------------ #

    async def _build_messages(self) -> List[Dict[str, Any]]:
        window = self._request.messages[-settings.assistant_history_max_messages:]
        last_user = window[-1].content

        knowledge_blocks, citations = await self._retriever.retrieve(last_user)
        self._citations = citations

        system_prompt = build_system_prompt(
            ctx=self._ctx,
            platform=self._request.platform,
            knowledge_blocks=knowledge_blocks,
            client_context=self._request.context,
        )

        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for message in window:
            content = message.content
            if message.role == "user":
                content = neutralize_sentinels(
                    sanitize_user_input(content, content_type="chat_message")
                )
            messages.append({"role": message.role, "content": content})
        return messages

    async def _one_completion(
        self, messages: List[Dict[str, Any]], allow_tools: bool
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        One streamed LLM call. Yields content_chunk events; terminates with an
        internal "_final" event carrying full content and parsed tool calls.
        """
        kwargs: Dict[str, Any] = dict(
            model=settings.assistant_model,
            messages=messages,
            temperature=settings.assistant_temperature,
            max_tokens=settings.assistant_max_tokens,
            stream=True,
        )
        if allow_tools:
            kwargs["tools"] = openai_tool_specs(
                include_read_tools=self._ctx.tools_available
            )

        stream = await self._create_stream(kwargs)

        content_parts: List[str] = []
        tool_calls: Dict[int, Dict[str, str]] = {}

        async for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage:
                self._token_count += usage.total_tokens or 0
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue
            if delta.content:
                content_parts.append(delta.content)
                yield {"type": "content_chunk", "content": delta.content}
            for tc in delta.tool_calls or []:
                slot = tool_calls.setdefault(
                    tc.index, {"id": "", "name": "", "arguments": ""}
                )
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] += tc.function.name
                if tc.function and tc.function.arguments:
                    slot["arguments"] += tc.function.arguments

        yield {
            "type": "_final",
            "content": "".join(content_parts),
            "tool_calls": [tool_calls[i] for i in sorted(tool_calls)] or None,
        }

    async def _create_stream(self, kwargs: Dict[str, Any]):
        """Create a streamed completion, with stream_options when supported."""
        global _STREAM_OPTIONS_SUPPORTED
        if _STREAM_OPTIONS_SUPPORTED is not False:
            try:
                return await self._openai.chat.completions.create(
                    **kwargs, stream_options={"include_usage": True}
                )
            except TypeError:
                _STREAM_OPTIONS_SUPPORTED = False
                logger.info(
                    "openai SDK lacks stream_options; token usage reporting disabled"
                )
        return await self._openai.chat.completions.create(**kwargs)

    async def _dispatch_tool(
        self, call: Dict[str, str], messages: List[Dict[str, Any]]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute/resolve one tool call and append its tool-result message."""
        name = call["name"]
        try:
            args = json.loads(call["arguments"] or "{}")
            if not isinstance(args, dict):
                args = {}
        except ValueError:
            args = {}

        if name == "suggest_navigation":
            result = self._handle_navigation(args)
        elif name == "propose_action":
            result = self._handle_proposal(args)
        elif name in tool_registry.READ_TOOLS:
            yield {"type": "tool_call_started", "tool": name}
            outcome = await self._executor.execute(name, args)
            status = "ok" if outcome.get("status") == "ok" else "error"
            self._tool_calls.append(
                ToolCallInfo(tool=name, status=status, error_code=outcome.get("code"))
            )
            yield {"type": "tool_call_completed", "tool": name, "status": status}
            result = shrink_result(outcome)
        else:
            result = json.dumps({"status": "error", "code": "UNKNOWN_TOOL"})

        if name in ("suggest_navigation", "propose_action") and self._actions:
            latest = self._actions[-1]
            if latest.get("_fresh"):
                latest.pop("_fresh", None)
                yield {"type": "action", "action": latest}

        messages.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "content": f"<TOOL_RESULT>{result}</TOOL_RESULT>",
        })

    def _handle_navigation(self, args: Dict[str, Any]) -> str:
        action = resolve_navigation(
            intent=str(args.get("intent", "")),
            platform=self._request.platform,
            notice_id=args.get("noticeId"),
        )
        if action is None:
            return json.dumps({"status": "error", "code": "UNKNOWN_INTENT"})
        payload = action.model_dump(by_alias=True, exclude_none=True)
        payload["_fresh"] = True
        self._actions.append(payload)
        return json.dumps({"status": "ok", "message": f"navigation button offered: {action.label}"})

    def _handle_proposal(self, args: Dict[str, Any]) -> str:
        try:
            action = build_confirm_action(
                kind=str(args.get("kind", "")),
                summary=str(args.get("summary", "")),
                params=args.get("params") or {},
            )
        except ToolValidationError as exc:
            return json.dumps({"status": "error", "code": "INVALID_ACTION", "message": str(exc)})
        payload = action.model_dump(by_alias=True)
        payload["_fresh"] = True
        self._actions.append(payload)
        return json.dumps({
            "status": "ok",
            "message": "confirmation card shown; the user must confirm before anything happens",
        })
