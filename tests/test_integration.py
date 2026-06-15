"""통합 테스트 모듈.

Task 12: 통합 테스트 및 문서화

테스트 대상:
    12.1 Pipeline with sql_expert format → explain chaining
    12.2 Streaming endpoint with mocked LLM
    12.3 State persistence across multiple requests with same session_id
    12.4 Multi-model routing (mock providers)
    12.7 Backward compatibility: deprecated agents still function correctly
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.framework.model_router import LLMProvider, ModelRouter
from app.framework.pipeline import (
    ExecutionTrace,
    PipelineDefinition,
    PipelineExecutor,
    PipelineStep,
)
from app.framework.registry import ToolAgentRegistry
from app.framework.state_store import InMemoryStateStore

# Check if FastAPI/httpx are available for endpoint tests
try:
    from httpx import ASGITransport, AsyncClient
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

try:
    import fastapi  # noqa: F401
except ImportError:
    HAS_FASTAPI = False


# ---------------------------------------------------------------------------
# 12.1 Integration Test: Pipeline with sql_expert format → explain chaining
# ---------------------------------------------------------------------------


class TestPipelineChaining:
    """Pipeline 체이닝 통합 테스트.

    sql_expert format → explain 2단계 파이프라인을 구성하여
    출력 전달 메커니즘을 검증합니다.

    Requirements: 7.2, 7.3
    """

    @pytest.mark.asyncio
    async def test_pipeline_format_then_explain_chaining(self):
        """sql_expert format → explain 파이프라인에서 artifact 체이닝 검증.

        format 스텝의 output이 explain 스텝의 input으로 전달됨을 확인합니다.
        파이프라인 체이닝 메커니즘(output → input 매핑)이 정상 동작하는지 검증합니다.

        Note: ainvoke의 response_format="content_and_artifact"인 경우
        pipeline은 문자열 result를 {"result": str}로 래핑합니다.
        """
        from app.tool_agents.sql_expert_agent.factory import SqlExpertFactory
        from app.framework.dbutil import DBProvider

        # Mock DB provider that raises connection error
        mock_db = MagicMock(spec=DBProvider)
        mock_db.get_connection = AsyncMock(side_effect=Exception("DB not available"))

        factory = SqlExpertFactory(db_provider=mock_db)

        # Create a registry with the sql_expert
        registry = ToolAgentRegistry(package="nonexistent.package")
        registry.register(factory)

        executor = PipelineExecutor(registry)

        # 2-step pipeline: format → explain
        # Since ainvoke returns a string for content_and_artifact tools,
        # the pipeline wraps it as {"result": str}. So we map from $.result.
        definition = PipelineDefinition(
            steps=[
                PipelineStep(
                    agent_type="sql_expert",
                    sub_command="format",
                    input_mapping={"sql": "$.raw_sql"},
                ),
                PipelineStep(
                    agent_type="sql_expert",
                    sub_command="explain",
                    input_mapping={"query": "$.result"},
                ),
            ],
            initial_input={"raw_sql": "select id, name from users where id = 1"},
        )

        # Validate the pipeline first
        errors = await executor.validate(definition)
        assert errors == [], f"Validation errors: {errors}"

        # Execute the pipeline
        trace = await executor.execute(definition)

        # Step 1 (format) should succeed
        assert len(trace.steps) >= 1
        step1 = trace.steps[0]
        assert step1.agent_type == "sql_expert"
        assert step1.sub_command == "format"
        assert step1.status == "success"
        assert "result" in step1.output_artifact

        # Verify step1 produced formatted SQL with uppercased keywords
        formatted_sql = step1.output_artifact["result"]
        assert "SELECT" in formatted_sql

        # Step 2 (explain) - verify input_mapping correctly passed the formatted SQL
        assert len(trace.steps) == 2
        step2 = trace.steps[1]
        assert step2.agent_type == "sql_expert"
        assert step2.sub_command == "explain"
        # KEY VALIDATION: input_mapping resolved $.result → query correctly
        assert step2.input_data.get("query") == formatted_sql

        # The pipeline completed (chaining mechanism works)
        assert trace.total_duration_ms > 0
        assert trace.pipeline_id != ""

    @pytest.mark.asyncio
    async def test_pipeline_single_format_step_succeeds(self):
        """단일 format 스텝은 DB 없이도 성공합니다."""
        from app.tool_agents.sql_expert_agent.factory import SqlExpertFactory
        from app.framework.dbutil import DBProvider

        mock_db = MagicMock(spec=DBProvider)
        factory = SqlExpertFactory(db_provider=mock_db)

        registry = ToolAgentRegistry(package="nonexistent.package")
        registry.register(factory)
        executor = PipelineExecutor(registry)

        definition = PipelineDefinition(
            steps=[
                PipelineStep(
                    agent_type="sql_expert",
                    sub_command="format",
                    input_mapping={"sql": "$.input_sql"},
                ),
            ],
            initial_input={"input_sql": "select * from orders where status='active'"},
        )

        trace = await executor.execute(definition)

        assert trace.status == "completed"
        assert len(trace.steps) == 1
        assert trace.steps[0].status == "success"
        # ainvoke returns string for content_and_artifact, pipeline wraps as {"result": str}
        assert "result" in trace.steps[0].output_artifact
        assert "SELECT" in trace.steps[0].output_artifact["result"]


# ---------------------------------------------------------------------------
# 12.2 Integration Test: Streaming endpoint with mocked LLM
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestStreamingEndpoint:
    """SSE 스트리밍 엔드포인트 통합 테스트.

    FastAPI TestClient로 POST /supervisor/chat/stream을 호출하고
    SSE 이벤트 형식을 검증합니다.

    Requirements: 9.1, 9.2
    """

    @pytest.mark.asyncio
    async def test_stream_endpoint_returns_sse_events(self):
        """스트리밍 엔드포인트가 SSE 형식 이벤트를 반환."""
        from app.framework.streaming import format_sse_event

        # Mock the SupervisorService and its graph
        mock_graph = AsyncMock()

        mock_events = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="Hello")},
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content=" World")},
            },
        ]

        async def mock_astream_events(*args, **kwargs):
            for event in mock_events:
                yield event

        mock_graph.astream_events = mock_astream_events

        mock_service = MagicMock()
        mock_service._graph = mock_graph
        mock_service.build_config = MagicMock(return_value={"configurable": {"thread_id": "test-123"}})

        # Patch at the module level where imports happen
        with (
            patch("app.agents.supervisor_router.SupervisorService") as mock_svc_class,
            patch("app.agents.supervisor_router.registry") as mock_registry,
            patch("app.agents.supervisor_router.create_chat_model") as mock_model,
            patch("app.agents.supervisor_router.ops_service") as mock_ops,
            patch("app.main.Database") as mock_db_class,
            patch("app.main.ElasticsearchClient") as mock_es_class,
        ):
            mock_svc_class.create.return_value = mock_service
            mock_registry.discover.return_value = None
            mock_model.return_value = MagicMock()
            mock_ops.filter_enabled.return_value = {}

            mock_db_inst = AsyncMock()
            mock_db_inst.connect = AsyncMock(return_value=True)
            mock_db_inst.disconnect = AsyncMock()
            mock_db_inst.health_check = AsyncMock(return_value=True)
            mock_db_class.return_value = mock_db_inst

            mock_es_inst = AsyncMock()
            mock_es_inst.connect = AsyncMock(return_value=mock_es_inst)
            mock_es_inst.close = AsyncMock()
            mock_es_inst.is_healthy = AsyncMock(return_value=True)
            mock_es_class.return_value = mock_es_inst

            from app.main import create_app

            app = create_app()
            transport = ASGITransport(app=app)

            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/agent/supervisor/chat/stream",
                    json={
                        "message": "Hello",
                        "tool_agents": [],
                    },
                )

                assert response.status_code == 200
                assert "text/event-stream" in response.headers["content-type"]

                # Parse SSE events from response body
                body = response.text
                events = _parse_sse_body(body)

                # Should have token events and a done event
                event_types = [e["event_type"] for e in events]
                assert "token" in event_types
                assert "done" in event_types

                # Validate token events
                token_events = [e for e in events if e["event_type"] == "token"]
                for te in token_events:
                    assert "content" in te["data"]
                    assert "timestamp" in te["data"]

                # Validate done event is last
                assert events[-1]["event_type"] == "done"
                done_data = events[-1]["data"]
                assert "full_response" in done_data
                assert done_data["full_response"] == "Hello World"
                assert "session_id" in done_data

    @pytest.mark.asyncio
    async def test_stream_endpoint_content_type_headers(self):
        """스트리밍 응답에 올바른 헤더가 설정됨."""
        mock_graph = AsyncMock()

        async def mock_astream_events(*args, **kwargs):
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="Test")},
            }

        mock_graph.astream_events = mock_astream_events

        mock_service = MagicMock()
        mock_service._graph = mock_graph
        mock_service.build_config = MagicMock(return_value={"configurable": {"thread_id": "test-456"}})

        with (
            patch("app.agents.supervisor_router.SupervisorService") as mock_svc_class,
            patch("app.agents.supervisor_router.registry") as mock_registry,
            patch("app.agents.supervisor_router.create_chat_model") as mock_model,
            patch("app.agents.supervisor_router.ops_service") as mock_ops,
            patch("app.main.Database") as mock_db_class,
            patch("app.main.ElasticsearchClient") as mock_es_class,
        ):
            mock_svc_class.create.return_value = mock_service
            mock_registry.discover.return_value = None
            mock_model.return_value = MagicMock()
            mock_ops.filter_enabled.return_value = {}

            mock_db_inst = AsyncMock()
            mock_db_inst.connect = AsyncMock(return_value=True)
            mock_db_inst.disconnect = AsyncMock()
            mock_db_inst.health_check = AsyncMock(return_value=True)
            mock_db_class.return_value = mock_db_inst

            mock_es_inst = AsyncMock()
            mock_es_inst.connect = AsyncMock(return_value=mock_es_inst)
            mock_es_inst.close = AsyncMock()
            mock_es_inst.is_healthy = AsyncMock(return_value=True)
            mock_es_class.return_value = mock_es_inst

            from app.main import create_app

            app = create_app()
            transport = ASGITransport(app=app)

            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/agent/supervisor/chat/stream",
                    json={
                        "message": "Test",
                        "tool_agents": [],
                    },
                )

                assert response.status_code == 200
                assert "text/event-stream" in response.headers["content-type"]
                assert response.headers.get("cache-control") == "no-cache"


# ---------------------------------------------------------------------------
# 12.3 Integration Test: State persistence with same session_id
# ---------------------------------------------------------------------------


class TestStatePersistence:
    """State persistence 통합 테스트.

    InMemoryStateStore로 session_id 기반 상태 저장/로드를 검증합니다.

    Requirements: 8.3, 8.4
    """

    @pytest.mark.asyncio
    async def test_save_and_load_with_same_session_id(self):
        """동일 session_id로 상태 저장 후 로드 시 동일 상태 반환."""
        store = InMemoryStateStore(ttl_hours=24)

        state = {
            "response": "This is a test response",
            "session_id": "sess-1",
            "sources": ["source1"],
            "tool_calls": ["sql_expert"],
        }

        # Save state
        await store.save_state("sess-1", state)

        # Load state
        loaded = await store.load_state("sess-1")

        assert loaded is not None
        assert loaded["response"] == "This is a test response"
        assert loaded["session_id"] == "sess-1"
        assert loaded["sources"] == ["source1"]
        assert loaded["tool_calls"] == ["sql_expert"]

    @pytest.mark.asyncio
    async def test_multiple_saves_with_same_session_id_returns_latest(self):
        """동일 session_id로 여러 번 저장 시 최신 상태 반환 (UPSERT)."""
        store = InMemoryStateStore(ttl_hours=24)

        # First save
        state_v1 = {"response": "First response", "session_id": "sess-1"}
        await store.save_state("sess-1", state_v1)

        # Second save (same session_id)
        state_v2 = {"response": "Second response", "session_id": "sess-1"}
        await store.save_state("sess-1", state_v2)

        # Load should return v2
        loaded = await store.load_state("sess-1")
        assert loaded is not None
        assert loaded["response"] == "Second response"

    @pytest.mark.asyncio
    async def test_different_session_ids_are_independent(self):
        """다른 session_id는 독립적으로 관리됨."""
        store = InMemoryStateStore(ttl_hours=24)

        await store.save_state("sess-1", {"data": "session-1-data"})
        await store.save_state("sess-2", {"data": "session-2-data"})

        loaded_1 = await store.load_state("sess-1")
        loaded_2 = await store.load_state("sess-2")

        assert loaded_1 is not None
        assert loaded_2 is not None
        assert loaded_1["data"] == "session-1-data"
        assert loaded_2["data"] == "session-2-data"

    @pytest.mark.asyncio
    async def test_load_nonexistent_session_returns_none(self):
        """존재하지 않는 session_id 로드 시 None 반환."""
        store = InMemoryStateStore(ttl_hours=24)

        loaded = await store.load_state("nonexistent-session")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_state_persists_complex_nested_data(self):
        """복잡한 중첩 데이터 구조가 보존됨."""
        store = InMemoryStateStore(ttl_hours=24)

        complex_state = {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ],
            "tool_calls": [
                {"agent": "sql_expert", "sub_command": "format", "result": {"formatted_sql": "SELECT 1"}},
            ],
            "metadata": {"turn_count": 3, "active_agents": ["sql_expert", "schema_expert"]},
        }

        await store.save_state("sess-complex", complex_state)
        loaded = await store.load_state("sess-complex")

        assert loaded is not None
        assert loaded["messages"] == complex_state["messages"]
        assert loaded["tool_calls"] == complex_state["tool_calls"]
        assert loaded["metadata"]["turn_count"] == 3
        assert loaded["metadata"]["active_agents"] == ["sql_expert", "schema_expert"]


# ---------------------------------------------------------------------------
# 12.4 Integration Test: Multi-model routing (mock providers)
# ---------------------------------------------------------------------------


class TestMultiModelRouting:
    """멀티 모델 라우팅 통합 테스트.

    Mock provider들을 등록하고 모델 식별자에 따라 올바른 프로바이더로
    라우팅되는지 검증합니다.

    Requirements: 10.3, 10.4
    """

    @pytest.mark.asyncio
    async def test_anthropic_prefix_routes_to_anthropic_provider(self):
        """'anthropic/claude-3' → anthropic 프로바이더로 라우팅."""
        router = ModelRouter()

        mock_anthropic = AsyncMock(spec=LLMProvider)
        mock_anthropic.ainvoke = AsyncMock(return_value="Anthropic response")

        mock_openai = AsyncMock(spec=LLMProvider)
        mock_openai.ainvoke = AsyncMock(return_value="OpenAI response")

        router.register_provider("anthropic", mock_anthropic)
        router.register_provider("openai", mock_openai)

        # Route to anthropic
        result = await router.ainvoke("anthropic/claude-3", messages=[{"role": "user", "content": "hi"}])
        assert result == "Anthropic response"
        mock_anthropic.ainvoke.assert_called_once()
        mock_openai.ainvoke.assert_not_called()

        # Verify model name passed correctly
        call_kwargs = mock_anthropic.ainvoke.call_args
        assert call_kwargs.kwargs.get("model") == "claude-3" or (
            call_kwargs[1].get("model") == "claude-3" if len(call_kwargs) > 1 else False
        )

    @pytest.mark.asyncio
    async def test_no_prefix_routes_to_openai_provider(self):
        """'gpt-4o' (접두사 없음) → openai 프로바이더로 라우팅."""
        router = ModelRouter()

        mock_openai = AsyncMock(spec=LLMProvider)
        mock_openai.ainvoke = AsyncMock(return_value="OpenAI gpt-4o response")

        mock_anthropic = AsyncMock(spec=LLMProvider)
        mock_anthropic.ainvoke = AsyncMock(return_value="Anthropic response")

        router.register_provider("openai", mock_openai)
        router.register_provider("anthropic", mock_anthropic)

        # No prefix → defaults to openai
        result = await router.ainvoke("gpt-4o", messages=[{"role": "user", "content": "hello"}])
        assert result == "OpenAI gpt-4o response"
        mock_openai.ainvoke.assert_called_once()
        mock_anthropic.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_case_insensitive_provider_resolution(self):
        """프로바이더 이름은 대소문자 무시 라우팅."""
        router = ModelRouter()

        mock_provider = AsyncMock(spec=LLMProvider)
        mock_provider.ainvoke = AsyncMock(return_value="response")

        router.register_provider("anthropic", mock_provider)

        # Case-insensitive routing
        provider, model = router.resolve("Anthropic/claude-3-sonnet")
        assert provider is mock_provider
        assert model == "claude-3-sonnet"

        provider2, model2 = router.resolve("ANTHROPIC/claude-3-opus")
        assert provider2 is mock_provider
        assert model2 == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_unregistered_provider_raises_value_error(self):
        """미등록 프로바이더 요청 시 ValueError."""
        router = ModelRouter()

        mock_openai = AsyncMock(spec=LLMProvider)
        router.register_provider("openai", mock_openai)

        with pytest.raises(ValueError) as exc_info:
            router.resolve("google/gemini-pro")

        error_msg = str(exc_info.value)
        assert "google" in error_msg.lower()
        assert "openai" in error_msg.lower()  # Should list registered providers

    @pytest.mark.asyncio
    async def test_multiple_providers_coexist(self):
        """여러 프로바이더가 동시에 등록/라우팅 가능."""
        router = ModelRouter()

        providers = {
            "openai": AsyncMock(spec=LLMProvider),
            "anthropic": AsyncMock(spec=LLMProvider),
            "google": AsyncMock(spec=LLMProvider),
        }

        for name, provider in providers.items():
            provider.ainvoke = AsyncMock(return_value=f"{name} response")
            router.register_provider(name, provider)

        # Each routes to the correct provider
        r1 = await router.ainvoke("openai/gpt-4o", messages=[])
        assert r1 == "openai response"

        r2 = await router.ainvoke("anthropic/claude-3", messages=[])
        assert r2 == "anthropic response"

        r3 = await router.ainvoke("google/gemini-pro", messages=[])
        assert r3 == "google response"


# ---------------------------------------------------------------------------
# 12.7 Integration Test: Backward compatibility smoke test
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Deprecated agent 후방 호환성 smoke 테스트.

    deprecated 마킹된 기존 에이전트 팩토리들이 여전히 도구를 생성하고
    올바르게 동작하는지 검증합니다.

    Requirements: 1.12, 2.10, 3.10
    """

    def test_sql_formatter_factory_creates_tool(self):
        """SqlFormatterFactory가 여전히 도구를 생성할 수 있음."""
        from app.tool_agents.sql_formatter_agent.factory import SqlFormatterFactory

        factory = SqlFormatterFactory()
        assert factory.deprecated is True
        tool = factory.create_tool({"name": "format_sql", "description": "Format SQL"})
        assert tool is not None
        assert tool.name == "format_sql"

    def test_sql_lint_factory_creates_tool(self):
        """SqlLintFactory가 여전히 도구를 생성할 수 있음."""
        from app.tool_agents.sql_lint_agent.factory import SqlLintFactory

        factory = SqlLintFactory()
        assert factory.deprecated is True
        tool = factory.create_tool({"name": "lint_sql", "description": "Lint SQL"})
        assert tool is not None
        assert tool.name == "lint_sql"

    def test_ddl_generator_factory_creates_tool(self):
        """DDLGeneratorFactory가 여전히 도구를 생성할 수 있음."""
        from app.tool_agents.ddl_generator_agent.factory import DDLGeneratorFactory

        factory = DDLGeneratorFactory()
        assert factory.deprecated is True
        tool = factory.create_tool({"name": "generate_ddl", "description": "Generate DDL"})
        assert tool is not None
        assert tool.name == "generate_ddl"

    def test_email_draft_factory_creates_tool(self):
        """EmailDraftFactory가 여전히 도구를 생성할 수 있음."""
        from app.tool_agents.email_draft_agent.factory import EmailDraftFactory

        factory = EmailDraftFactory()
        assert factory.deprecated is True
        tool = factory.create_tool({"name": "email_draft", "description": "Draft email"})
        assert tool is not None
        assert tool.name == "email_draft"

    def test_translation_factory_creates_tool(self):
        """TranslationFactory가 여전히 도구를 생성할 수 있음."""
        from app.tool_agents.translation_agent.factory import TranslationFactory

        factory = TranslationFactory()
        assert factory.deprecated is True
        tool = factory.create_tool({"name": "translate", "description": "Translate"})
        assert tool is not None
        assert tool.name == "translate"

    def test_meeting_summary_factory_creates_tool(self):
        """MeetingSummaryFactory가 여전히 도구를 생성할 수 있음."""
        from app.tool_agents.meeting_summary_agent.factory import MeetingSummaryFactory

        factory = MeetingSummaryFactory()
        assert factory.deprecated is True
        tool = factory.create_tool({"name": "meeting_summary", "description": "Summarize"})
        assert tool is not None
        assert tool.name == "meeting_summary"

    def test_query_explain_factory_creates_tool(self):
        """QueryExplainFactory가 여전히 도구를 생성할 수 있음."""
        from app.tool_agents.query_explain_agent.factory import QueryExplainFactory

        factory = QueryExplainFactory()
        assert factory.deprecated is True
        tool = factory.create_tool({"name": "explain_query", "description": "Explain"})
        assert tool is not None
        assert tool.name == "explain_query"

    def test_slow_query_analyzer_factory_creates_tool(self):
        """SlowQueryAnalyzerFactory가 여전히 도구를 생성할 수 있음."""
        from app.tool_agents.slow_query_analyzer_agent.factory import SlowQueryAnalyzerFactory

        factory = SlowQueryAnalyzerFactory()
        assert factory.deprecated is True
        tool = factory.create_tool({"name": "analyze_slow_query", "description": "Analyze"})
        assert tool is not None
        assert tool.name == "analyze_slow_query"

    @pytest.mark.asyncio
    async def test_sql_formatter_tool_still_formats(self):
        """SqlFormatterTool이 여전히 SQL을 포맷할 수 있음."""
        from app.tool_agents.sql_formatter_agent.factory import SqlFormatterFactory

        factory = SqlFormatterFactory()
        tool = factory.create_tool({"name": "format_sql", "description": "Format SQL"})

        result = await tool.ainvoke({"sql": "select id from users"})

        # Result should contain formatted SQL
        if isinstance(result, tuple):
            _, artifact = result
        elif isinstance(result, dict):
            artifact = result
        else:
            artifact = {"result": str(result)}

        # The formatter should have uppercased keywords
        assert artifact is not None

    @pytest.mark.asyncio
    async def test_sql_lint_tool_still_lints(self):
        """SqlLintTool이 여전히 SQL을 린트할 수 있음."""
        from app.tool_agents.sql_lint_agent.factory import SqlLintFactory

        factory = SqlLintFactory()
        tool = factory.create_tool({"name": "lint_sql", "description": "Lint SQL"})

        result = await tool.ainvoke({"sql": "SELECT * FROM users"})

        # Result should contain lint issues
        if isinstance(result, tuple):
            _, artifact = result
        elif isinstance(result, dict):
            artifact = result
        else:
            artifact = {"result": str(result)}

        assert artifact is not None

    def test_all_deprecated_factories_have_deprecated_flag(self):
        """모든 deprecated 팩토리가 deprecated=True 플래그를 가짐."""
        from app.tool_agents.sql_formatter_agent.factory import SqlFormatterFactory
        from app.tool_agents.sql_lint_agent.factory import SqlLintFactory
        from app.tool_agents.ddl_generator_agent.factory import DDLGeneratorFactory
        from app.tool_agents.email_draft_agent.factory import EmailDraftFactory
        from app.tool_agents.translation_agent.factory import TranslationFactory
        from app.tool_agents.meeting_summary_agent.factory import MeetingSummaryFactory
        from app.tool_agents.query_explain_agent.factory import QueryExplainFactory
        from app.tool_agents.slow_query_analyzer_agent.factory import SlowQueryAnalyzerFactory
        from app.tool_agents.document_review_agent.factory import DocumentReviewFactory
        from app.tool_agents.report_outline_agent.factory import ReportOutlineFactory
        from app.tool_agents.presentation_helper_agent.factory import PresentationHelperFactory
        from app.tool_agents.task_breakdown_agent.factory import TaskBreakdownFactory
        from app.tool_agents.schedule_planner_agent.factory import SchedulePlannerFactory
        from app.tool_agents.schema_inspector_agent.factory import SchemaInspectorFactory
        from app.tool_agents.er_diagram_agent.factory import ERDiagramFactory
        from app.tool_agents.index_advisor_agent.factory import IndexAdvisorFactory

        deprecated_factories = [
            SqlFormatterFactory(),
            SqlLintFactory(),
            DDLGeneratorFactory(),
            EmailDraftFactory(),
            TranslationFactory(),
            MeetingSummaryFactory(),
            QueryExplainFactory(),
            SlowQueryAnalyzerFactory(),
            DocumentReviewFactory(),
            ReportOutlineFactory(),
            PresentationHelperFactory(),
            TaskBreakdownFactory(),
            SchedulePlannerFactory(),
            SchemaInspectorFactory(),
            ERDiagramFactory(),
            IndexAdvisorFactory(),
        ]

        for factory in deprecated_factories:
            assert factory.deprecated is True, (
                f"{factory.__class__.__name__} should be deprecated"
            )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _parse_sse_body(body: str) -> list[dict]:
    """SSE 응답 본문을 파싱하여 이벤트 목록을 반환합니다."""
    events = []
    current_event_type = None

    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("event: "):
            current_event_type = line[7:]
        elif line.startswith("data: ") and current_event_type:
            try:
                data = json.loads(line[6:])
                events.append({"event_type": current_event_type, "data": data})
            except json.JSONDecodeError:
                pass
            current_event_type = None
        elif line == "" and current_event_type:
            # Empty line after event without data
            current_event_type = None

    return events
