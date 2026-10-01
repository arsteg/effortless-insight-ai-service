"""
Assistant tool registry and executor.

Three kinds of model-callable tools:
1. READ tools — whitelisted GET endpoints on the backend API, executed here
   on the user's behalf with their forwarded JWT. The backend enforces
   tenant, role, feature, and usage limits; this module only constrains
   WHICH endpoints and parameters are reachable at all.
2. suggest_navigation — resolved locally against knowledge/product/screen-map.json.
3. propose_action — validated locally against the confirm-action catalog and
   emitted to the client as a confirmation card. NEVER executed server-side.

Anything not in this module cannot be called, regardless of what the model asks.
The declarative mirror of this registry lives in knowledge/product/tools.json;
a unit test keeps the two in sync.
"""

import json
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
import structlog

from app.core.config import settings
from app.schemas.assistant import ConfirmAction, NavigateAction
from app.services.assistant.context import AssistantContext
from app.services.rag.product_knowledge import load_screen_map

logger = structlog.get_logger()

UUID_RE = re.compile(r"^[0-9a-fA-F-]{32,36}$")

# Fields stripped from tool results before they reach the model (heavy/noisy).
HEAVY_FIELDS = {"ocrText", "fullReportJson", "contentHtml", "rawData", "metadata"}
MAX_RESULT_CHARS = 6000
MAX_LIST_ITEMS = 20


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


# name -> definition. "params" maps model-arg name -> ("query"|"path", validator)
READ_TOOLS: Dict[str, Dict[str, Any]] = {
    "get_notices": {
        "path": "/api/v1/notices",
        "description": "List the user's GST notices with optional filters.",
        "query_params": {
            "status", "priority", "search", "gstin",
            "deadlineFrom", "deadlineTo", "overdue", "dueWithinDays",
            "page", "pageSize", "sortBy", "sortOrder",
        },
        "schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "uploaded|processing|analyzed|in_progress|responded|closed|archived"},
                "priority": {"type": "string", "description": "low|medium|high|critical"},
                "search": {"type": "string"},
                "gstin": {"type": "string"},
                "overdue": {"type": "boolean"},
                "dueWithinDays": {"type": "integer"},
                "pageSize": {"type": "integer", "description": "max 20"},
                "sortBy": {"type": "string", "description": "e.g. deadline"},
                "sortOrder": {"type": "string", "description": "asc|desc"},
            },
        },
    },
    "get_notice": {
        "path": "/api/v1/notices/{noticeId}",
        "description": "Get one notice's details (type, status, deadline, amounts, assignee).",
        "path_params": ["noticeId"],
        "schema": {
            "type": "object",
            "properties": {"noticeId": {"type": "string", "description": "notice UUID"}},
            "required": ["noticeId"],
        },
    },
    "get_notice_report": {
        "path": "/api/v1/notices/{noticeId}/report",
        "description": "Get the AI analysis report of a notice (risk, summaries, action items). May be plan-gated.",
        "path_params": ["noticeId"],
        "schema": {
            "type": "object",
            "properties": {"noticeId": {"type": "string", "description": "notice UUID"}},
            "required": ["noticeId"],
        },
    },
    "get_notice_statistics": {
        "path": "/api/v1/notices/statistics",
        "description": "Counts of the user's notices by status/priority plus due-soon and overdue totals.",
        "query_params": set(),
        "schema": {"type": "object", "properties": {}},
    },
    "get_upcoming_deadlines": {
        "path": "/api/v1/notices",
        "description": "Notices with response deadlines coming up, soonest first.",
        "query_params": {"dueWithinDays", "pageSize", "sortBy", "sortOrder"},
        "defaults": {"dueWithinDays": 14, "pageSize": 10, "sortBy": "deadline", "sortOrder": "asc"},
        "schema": {
            "type": "object",
            "properties": {"dueWithinDays": {"type": "integer", "description": "default 14"}},
        },
    },
    "get_my_tasks": {
        "path": "/api/v1/tasks",
        "description": "The user's open tasks, optionally due within a window.",
        "query_params": {"assignedToMe", "dueWithin", "status"},
        "defaults": {"assignedToMe": True},
        "schema": {
            "type": "object",
            "properties": {
                "dueWithin": {"type": "string", "description": "week|month"},
                "status": {"type": "string"},
            },
        },
    },
    "get_subscription_usage": {
        "path": "/api/v1/usage",
        "description": "Current plan, trial status, and usage against limits (notices, seats, GSTINs, storage).",
        "query_params": set(),
        "schema": {"type": "object", "properties": {}},
    },
    "get_members": {
        "path": "/api/v1/organizations/{orgId}/members",
        "description": "Members of the current organization (names, roles, status).",
        "path_params": ["orgId"],  # injected from context, never from the model
        "inject_org": True,
        "schema": {"type": "object", "properties": {}},
    },
}

# kind -> definition for propose_action. Body keys are a whitelist; path params
# are UUID-validated. The AI service never executes these.
CONFIRM_KINDS: Dict[str, Dict[str, Any]] = {
    "auto_draft": {
        "method": "POST",
        "path": "/api/v1/notices/{noticeId}/responses/auto-draft",
        "path_params": ["noticeId"],
        "body_keys": {"tone", "language"},
        "body_defaults": {"tone": "formal", "language": "en"},
    },
    "create_task": {
        "method": "POST",
        "path": "/api/v1/tasks",
        "path_params": [],
        "body_keys": {"noticeId", "title", "description", "dueDate"},
        "body_defaults": {},
    },
    "add_reminder": {
        "method": "POST",
        "path": "/api/v1/notices/{noticeId}/reminders",
        "path_params": ["noticeId"],
        "body_keys": {"remindAt", "note"},
        "body_defaults": {},
    },
    "update_status": {
        "method": "PUT",
        "path": "/api/v1/notices/{noticeId}/status",
        "path_params": ["noticeId"],
        "body_keys": {"status"},
        "body_defaults": {},
        "allowed_values": {"status": {"in_progress", "responded", "closed"}},
    },
}

LOCAL_TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "suggest_navigation",
            "description": (
                "Offer the user a button to open a screen in the app. Use whenever a "
                "screen is (part of) the answer. intent must be one of the known intents."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string", "description": "screen intent key, e.g. notices_list, settings_billing, team"},
                    "noticeId": {"type": "string", "description": "notice UUID when the intent targets one notice"},
                },
                "required": ["intent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_action",
            "description": (
                "Propose a supported write action for the user to confirm (a confirmation "
                "card is shown; the app executes it only after the user taps Confirm). "
                "kinds: auto_draft, create_task, add_reminder, update_status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "description": "auto_draft|create_task|add_reminder|update_status"},
                    "summary": {"type": "string", "description": "one sentence describing exactly what will happen"},
                    "params": {"type": "object", "description": "action parameters, e.g. noticeId, tone, title, dueDate, status"},
                },
                "required": ["kind", "summary", "params"],
            },
        },
    },
]


def openai_tool_specs(include_read_tools: bool = True) -> List[Dict[str, Any]]:
    """Tool specs for the OpenAI chat API."""
    specs: List[Dict[str, Any]] = []
    if include_read_tools:
        for name, definition in READ_TOOLS.items():
            specs.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": definition["description"],
                    "parameters": definition["schema"],
                },
            })
    specs.extend(LOCAL_TOOL_SPECS)
    return specs


def _validate_uuid(value: Any, name: str) -> str:
    value = str(value or "")
    if not UUID_RE.match(value):
        raise ToolValidationError(f"{name} must be a UUID")
    try:
        UUID(value)
    except ValueError:
        raise ToolValidationError(f"{name} must be a UUID")
    return value


class ToolValidationError(Exception):
    """Model supplied arguments that fail whitelist validation."""


def _prune(value: Any, depth: int = 0) -> Any:
    """Strip heavy fields and clamp list sizes before showing data to the model."""
    if isinstance(value, dict):
        return {
            k: _prune(v, depth + 1)
            for k, v in value.items()
            if k not in HEAVY_FIELDS
        }
    if isinstance(value, list):
        return [_prune(item, depth + 1) for item in value[:MAX_LIST_ITEMS]]
    if isinstance(value, str) and len(value) > 1000:
        return value[:1000] + "…"
    return value


def shrink_result(payload: Any) -> str:
    """Serialize a tool result for the model, bounded in size."""
    pruned = _prune(payload)
    text = json.dumps(pruned, ensure_ascii=False, default=str)
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + "…(truncated)"
    return text


class ToolExecutor:
    """Executes whitelisted READ tools against the backend API as the user."""

    def __init__(self, ctx: AssistantContext, http_client: Optional[httpx.AsyncClient] = None):
        self._ctx = ctx
        self._client = http_client

    async def execute(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run one read tool. Returns {"status": "ok"|"error", ...}; errors are
        structured so the model can explain them (never retried here).
        """
        definition = READ_TOOLS.get(name)
        if definition is None:
            return {"status": "error", "code": "UNKNOWN_TOOL", "message": f"tool {name} does not exist"}
        if not self._ctx.tools_available:
            return {"status": "error", "code": "NO_USER_TOKEN", "message": "live data is unavailable right now"}

        try:
            path = self._build_path(definition, args)
            params = self._build_query(definition, args)
        except ToolValidationError as exc:
            return {"status": "error", "code": "INVALID_ARGS", "message": str(exc)}

        url = settings.api_service_url.rstrip("/") + path
        headers = {"Authorization": f"Bearer {self._ctx.user_token}"}

        try:
            if self._client is not None:
                response = await self._client.get(url, params=params, headers=headers)
            else:
                async with httpx.AsyncClient(
                    timeout=settings.assistant_tool_timeout_seconds
                ) as client:
                    response = await client.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("Assistant tool call failed", tool=name, error=type(exc).__name__)
            return {"status": "error", "code": "BACKEND_UNAVAILABLE", "message": "could not reach the app backend"}

        if response.status_code == 402:
            return {"status": "error", "code": "FEATURE_NOT_AVAILABLE", "message": "this feature is not in the user's plan"}
        if response.status_code == 403:
            return {"status": "error", "code": "FORBIDDEN", "message": "the user's role does not allow this"}
        if response.status_code == 404:
            return {"status": "error", "code": "NOT_FOUND", "message": "not found"}
        if response.status_code == 401:
            return {"status": "error", "code": "UNAUTHORIZED", "message": "the user's session expired"}
        if response.status_code >= 400:
            logger.warning("Assistant tool call error", tool=name, status=response.status_code)
            return {"status": "error", "code": f"HTTP_{response.status_code}", "message": "backend error"}

        try:
            payload = response.json()
        except ValueError:
            return {"status": "error", "code": "BAD_RESPONSE", "message": "unreadable backend response"}

        # Unwrap the standard {success, data} envelope; tolerate bare payloads.
        if isinstance(payload, dict) and "data" in payload and "success" in payload:
            payload = payload["data"]

        return {"status": "ok", "data": payload}

    def _build_path(self, definition: Dict[str, Any], args: Dict[str, Any]) -> str:
        path: str = definition["path"]
        for param in definition.get("path_params", []):
            if param == "orgId" and definition.get("inject_org"):
                value = str(self._ctx.organization_id)
            else:
                value = _validate_uuid(args.get(param), param)
            path = path.replace("{" + param + "}", value)
        if "{" in path:
            raise ToolValidationError("unresolved path parameter")
        return path

    def _build_query(self, definition: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        allowed = definition.get("query_params", set())
        params: Dict[str, Any] = dict(definition.get("defaults", {}))
        for key, value in args.items():
            if key in allowed and value is not None:
                params[key] = value
        if "pageSize" in allowed:
            params["pageSize"] = _clamp_int(params.get("pageSize"), 1, 20, 10)
        if "dueWithinDays" in params:
            params["dueWithinDays"] = _clamp_int(params.get("dueWithinDays"), 1, 90, 14)
        return params


def resolve_navigation(
    intent: str,
    platform: str,
    notice_id: Optional[str] = None,
    screen_map: Optional[Dict[str, Any]] = None,
) -> Optional[NavigateAction]:
    """Resolve a screen intent into a NavigateAction, or None if unknown."""
    screen_map = screen_map or load_screen_map()
    entry = (screen_map.get("intents") or {}).get(intent)
    if not entry:
        return None

    def fill(route: Optional[str]) -> Optional[str]:
        if route and "{noticeId}" in route:
            if not notice_id:
                return None
            try:
                _validate_uuid(notice_id, "noticeId")
            except ToolValidationError:
                return None
            return route.replace("{noticeId}", str(notice_id))
        return route

    return NavigateAction(
        intent=intent,
        label=entry.get("label", intent),
        web_route=fill(entry.get("web")),
        mobile_route=fill(entry.get("mobile")),
        web_only_note=entry.get("webOnlyNote") if entry.get("mobile") is None else None,
    )


def build_confirm_action(kind: str, summary: str, params: Dict[str, Any]) -> ConfirmAction:
    """
    Validate a model-proposed write and shape it into a ConfirmAction.
    Raises ToolValidationError on anything outside the catalog.
    """
    definition = CONFIRM_KINDS.get(kind)
    if definition is None:
        raise ToolValidationError(f"unsupported action kind: {kind}")

    path: str = definition["path"]
    for param in definition["path_params"]:
        value = _validate_uuid(params.get(param), param)
        path = path.replace("{" + param + "}", value)

    body = dict(definition["body_defaults"])
    for key in definition["body_keys"]:
        if key in params and params[key] is not None:
            body[key] = params[key]
    for key, allowed_values in definition.get("allowed_values", {}).items():
        if body.get(key) not in allowed_values:
            raise ToolValidationError(f"{key} must be one of {sorted(allowed_values)}")
    # body noticeId (create_task) must be a UUID when present
    if "noticeId" in body:
        body["noticeId"] = _validate_uuid(body["noticeId"], "noticeId")

    summary = (summary or "").strip()[:300]
    if not summary:
        raise ToolValidationError("summary is required")

    return ConfirmAction(
        kind=kind,
        summary=summary,
        method=definition["method"],
        path=path,
        body=body,
    )
