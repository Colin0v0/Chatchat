import asyncio
from types import SimpleNamespace

from app.retrieval.types import ContextPayload
from app.retrieval.query_rewrite import QueryRewriteResult
from app.tools import build_tool_context_plan, build_tool_policy
from app.tools.requests import ToolContextBuildRequest, ToolPlanRequest
from app.tools.service import ToolRuntimeService


def test_plan_context_accepts_structured_request():
    service = ToolRuntimeService.__new__(ToolRuntimeService)

    plan = service.plan_context(
        request=ToolPlanRequest(query="what is pgvector", tool_policy=build_tool_policy("search"))
    )

    assert plan.mode == "search"
    assert plan.policy.mode == "search"
    assert plan.query == "what is pgvector"
    assert plan.requested_tools == ("search",)


def test_tool_context_build_request_carries_runtime_inputs():
    request = ToolContextBuildRequest(
        db=SimpleNamespace(),
        user_id=7,
        query="hello",
        plan=SimpleNamespace(mode="none", query="", requested_tools=(), strategy=SimpleNamespace(name="direct")),
        retrieval_messages=[{"role": "user", "content": "hello"}],
        conversation_messages=[],
        include_file_context=False,
        include_image_context=False,
    )

    assert request.user_id == 7
    assert request.query == "hello"
    assert request.include_file_context is False


def test_build_context_payload_does_not_refuse_when_attachment_context_is_empty():
    class _FileContextService:
        async def retrieve_context(self, **kwargs):
            return ContextPayload(entries=[], sources=[], debug={"file_hits": 0})

    service = ToolRuntimeService.__new__(ToolRuntimeService)
    service._knowledge_service = SimpleNamespace()
    service._web_search_service = SimpleNamespace()
    service._file_context_service = _FileContextService()
    service._context_top_k = 4

    async def _fake_rewrite(*, plan, retrieval_messages):
        return QueryRewriteResult(
            original_query=plan.query,
            effective_query=plan.query,
            applied=False,
            model=None,
            context_message_count=0,
        )

    service._rewrite_query = _fake_rewrite

    plan = build_tool_context_plan(query="", policy=build_tool_policy("none"))
    payload = asyncio.run(
        service.build_context_payload(
            request=ToolContextBuildRequest(
                db=SimpleNamespace(),
                user_id=7,
                query="这是什么游戏",
                plan=plan,
                retrieval_messages=[{"role": "user", "content": "这是什么游戏"}],
                conversation_messages=[],
                include_file_context=True,
                include_image_context=False,
            )
        )
    )

    assert payload.context_message is None
    assert payload.should_refuse is False
    assert payload.refusal_message is None
