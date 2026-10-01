"""
Unit tests for the assistant tool registry, executor, navigation resolver,
and confirm-action builder (app/services/assistant/tools.py).
"""

import json
from uuid import UUID, uuid4

import httpx
import pytest

from app.core.config import settings
from app.services.assistant.context import AssistantContext
from app.services.assistant import tools as tool_module
from app.services.assistant.tools import (
    CONFIRM_KINDS,
    READ_TOOLS,
    ToolExecutor,
    ToolValidationError,
    build_confirm_action,
    openai_tool_specs,
    resolve_navigation,
    shrink_result,
)
from app.services.rag.product_knowledge import load_tool_registry

ORG_ID = uuid4()


def make_ctx(token="user-jwt-token") -> AssistantContext:
    return AssistantContext(
        organization_id=ORG_ID,
        user_id="user-1",
        user_role="member",
        plan="team",
        user_token=token,
    )


def make_executor(ctx, handler) -> ToolExecutor:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return ToolExecutor(ctx, http_client=client)


class TestRegistryIntegrity:
    def test_code_registry_matches_declarative_tools_json(self):
        declared = load_tool_registry()
        declared_reads = {tool["name"] for tool in declared["read_tools"]}
        assert declared_reads == set(READ_TOOLS.keys())
        declared_kinds = {action["kind"] for action in declared["confirm_actions"]}
        assert declared_kinds == set(CONFIRM_KINDS.keys())

    def test_openai_specs_include_local_tools(self):
        names = {spec["function"]["name"] for spec in openai_tool_specs()}
        assert "suggest_navigation" in names and "propose_action" in names
        assert "get_notices" in names

    def test_specs_without_read_tools_when_no_token(self):
        names = {
            spec["function"]["name"]
            for spec in openai_tool_specs(include_read_tools=False)
        }
        assert names == {"suggest_navigation", "propose_action"}

    def test_no_write_methods_in_read_registry(self):
        # every read tool is executed via GET only; registry has no method field
        for definition in READ_TOOLS.values():
            assert "delete" not in definition["path"].lower()

    def test_context_repr_hides_token(self):
        ctx = make_ctx("SECRET-TOKEN")
        assert "SECRET-TOKEN" not in repr(ctx)


class TestToolExecutor:
    async def test_unknown_tool(self):
        executor = make_executor(make_ctx(), lambda request: httpx.Response(200))
        result = await executor.execute("delete_everything", {})
        assert result["code"] == "UNKNOWN_TOOL"

    async def test_no_token_blocks_execution(self):
        executor = make_executor(make_ctx(token=None), lambda request: httpx.Response(200))
        result = await executor.execute("get_notices", {})
        assert result["code"] == "NO_USER_TOKEN"

    async def test_invalid_uuid_arg(self):
        executor = make_executor(make_ctx(), lambda request: httpx.Response(200))
        result = await executor.execute("get_notice", {"noticeId": "1 OR 1=1"})
        assert result["code"] == "INVALID_ARGS"

    async def test_happy_path_unwraps_envelope_and_sends_bearer(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["auth"] = request.headers.get("Authorization")
            return httpx.Response(200, json={"success": True, "data": {"items": [1, 2]}})

        executor = make_executor(make_ctx(), handler)
        result = await executor.execute("get_notices", {"status": "analyzed"})

        assert result == {"status": "ok", "data": {"items": [1, 2]}}
        assert seen["auth"] == "Bearer user-jwt-token"
        assert seen["url"].startswith(settings.api_service_url.rstrip("/") + "/api/v1/notices")
        assert "status=analyzed" in seen["url"]

    async def test_bare_payload_tolerated(self):
        executor = make_executor(
            make_ctx(), lambda request: httpx.Response(200, json=[{"id": 1}])
        )
        result = await executor.execute("get_my_tasks", {})
        assert result["status"] == "ok"
        assert result["data"] == [{"id": 1}]

    async def test_org_id_injected_from_context_not_model(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            return httpx.Response(200, json={"success": True, "data": []})

        executor = make_executor(make_ctx(), handler)
        # model tries to read another org's members — its orgId must be ignored
        await executor.execute("get_members", {"orgId": str(uuid4())})
        assert str(ORG_ID) in seen["url"]

    async def test_page_size_clamped(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["params"] = dict(request.url.params)
            return httpx.Response(200, json={"success": True, "data": []})

        executor = make_executor(make_ctx(), handler)
        await executor.execute("get_notices", {"pageSize": 500})
        assert seen["params"]["pageSize"] == "20"

    @pytest.mark.parametrize(
        "status,code",
        [(402, "FEATURE_NOT_AVAILABLE"), (403, "FORBIDDEN"), (404, "NOT_FOUND"), (401, "UNAUTHORIZED"), (500, "HTTP_500")],
    )
    async def test_http_errors_mapped(self, status, code):
        executor = make_executor(
            make_ctx(), lambda request: httpx.Response(status, json={})
        )
        result = await executor.execute("get_notice_statistics", {})
        assert result["status"] == "error"
        assert result["code"] == code

    async def test_network_failure(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        executor = make_executor(make_ctx(), handler)
        result = await executor.execute("get_notice_statistics", {})
        assert result["code"] == "BACKEND_UNAVAILABLE"


class TestShrinkResult:
    def test_heavy_fields_stripped_and_lists_clamped(self):
        payload = {
            "ocrText": "x" * 50000,
            "items": [{"id": i, "fullReportJson": {"big": True}} for i in range(100)],
        }
        text = shrink_result(payload)
        data = json.loads(text) if not text.endswith("…(truncated)") else None
        assert "ocrText" not in text
        assert "fullReportJson" not in text
        if data:
            assert len(data["items"]) <= 20

    def test_hard_char_cap(self):
        payload = {"notes": ["a" * 900 for _ in range(20)]}
        assert len(shrink_result(payload)) <= tool_module.MAX_RESULT_CHARS + 20


class TestResolveNavigation:
    def test_known_intent(self):
        action = resolve_navigation("notices_list", "web")
        assert action is not None
        assert action.web_route == "/notices"
        assert action.mobile_route == "/(tabs)/notices"

    def test_unknown_intent(self):
        assert resolve_navigation("admin_portal", "web") is None

    def test_notice_id_filled(self):
        notice_id = str(uuid4())
        action = resolve_navigation("notice_detail", "web", notice_id=notice_id)
        assert action.web_route == f"/notices/{notice_id}"

    def test_notice_intent_without_id_gives_no_route(self):
        action = resolve_navigation("notice_detail", "web")
        assert action.web_route is None

    def test_invalid_notice_id_rejected(self):
        action = resolve_navigation("notice_detail", "web", notice_id="../../etc")
        assert action.web_route is None

    def test_web_only_intent_carries_note(self):
        action = resolve_navigation("gst_sync", "mobile")
        assert action.mobile_route is None
        assert action.web_only_note


class TestBuildConfirmAction:
    def test_auto_draft(self):
        notice_id = str(uuid4())
        action = build_confirm_action(
            "auto_draft", "Draft a formal reply", {"noticeId": notice_id, "tone": "formal"}
        )
        assert action.method == "POST"
        assert action.path == f"/api/v1/notices/{notice_id}/responses/auto-draft"
        assert action.body == {"tone": "formal", "language": "en"}

    def test_unknown_kind_rejected(self):
        with pytest.raises(ToolValidationError):
            build_confirm_action("delete_notice", "del", {"noticeId": str(uuid4())})

    def test_update_status_whitelist(self):
        with pytest.raises(ToolValidationError):
            build_confirm_action(
                "update_status", "archive it", {"noticeId": str(uuid4()), "status": "archived"}
            )

    def test_extra_body_keys_dropped(self):
        action = build_confirm_action(
            "create_task",
            "Create a task",
            {"noticeId": str(uuid4()), "title": "Reply", "isAdmin": True, "orgId": "x"},
        )
        assert "isAdmin" not in action.body and "orgId" not in action.body

    def test_summary_required(self):
        with pytest.raises(ToolValidationError):
            build_confirm_action("create_task", "  ", {"title": "x"})

    def test_bad_uuid_rejected(self):
        with pytest.raises(ToolValidationError):
            build_confirm_action("add_reminder", "remind", {"noticeId": "not-a-uuid"})
