"""SSE 스트리밍 응답 유닛 테스트.

Property 18: SSE 이벤트 형식 및 순서 검증.
Validates: Requirements 9.3, 9.4, 9.6, 9.7

테스트 항목:
    - SSE 이벤트 포맷 검증 (event: {type}\\ndata: {json}\\n\\n)
    - token 이벤트 필드 검증 (content, timestamp)
    - error 이벤트 발생 검증
    - done 이벤트가 마지막 이벤트 검증
    - heartbeat 포맷 검증
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st

from app.framework.streaming import (
    SSEEvent,
    VALID_EVENT_TYPES,
    format_heartbeat,
    format_sse_event,
    stream_supervisor_response,
    _classify_error,
    _now_iso,
)


# ---------------------------------------------------------------------------
# Unit Tests: format_sse_event
# ---------------------------------------------------------------------------


class TestFormatSSEEvent:
    """format_sse_event 함수 테스트."""

    def test_basic_token_event_format(self):
        """token 이벤트의 기본 형식이 올바른지 확인."""
        data = {"content": "Hello", "timestamp": "2024-01-01T00:00:00+00:00"}
        result = format_sse_event("token", data)

        assert result.startswith("event: token\n")
        assert "data: " in result
        assert result.endswith("\n\n")

        # Parse the data line
        lines = result.strip().split("\n")
        assert lines[0] == "event: token"
        data_line = lines[1]
        assert data_line.startswith("data: ")
        parsed = json.loads(data_line[6:])
        assert parsed["content"] == "Hello"
        assert parsed["timestamp"] == "2024-01-01T00:00:00+00:00"

    def test_tool_call_event_format(self):
        """tool_call 이벤트 형식 확인."""
        data = {
            "agent_type": "sql_expert",
            "sub_command": "format",
            "timestamp": "2024-01-01T00:00:00+00:00",
        }
        result = format_sse_event("tool_call", data)

        lines = result.strip().split("\n")
        assert lines[0] == "event: tool_call"
        parsed = json.loads(lines[1][6:])
        assert parsed["agent_type"] == "sql_expert"
        assert parsed["sub_command"] == "format"

    def test_tool_result_event_format(self):
        """tool_result 이벤트 형식 확인."""
        data = {
            "artifact": {"formatted_sql": "SELECT 1"},
            "timestamp": "2024-01-01T00:00:00+00:00",
        }
        result = format_sse_event("tool_result", data)

        lines = result.strip().split("\n")
        assert lines[0] == "event: tool_result"
        parsed = json.loads(lines[1][6:])
        assert parsed["artifact"]["formatted_sql"] == "SELECT 1"

    def test_done_event_format(self):
        """done 이벤트 형식 확인."""
        data = {
            "full_response": "Analysis complete.",
            "session_id": "sess-123",
            "tool_calls": ["sql_expert"],
        }
        result = format_sse_event("done", data)

        lines = result.strip().split("\n")
        assert lines[0] == "event: done"
        parsed = json.loads(lines[1][6:])
        assert parsed["full_response"] == "Analysis complete."
        assert parsed["session_id"] == "sess-123"
        assert parsed["tool_calls"] == ["sql_expert"]

    def test_error_event_format(self):
        """error 이벤트 형식 확인."""
        data = {
            "error_message": "LLM generation failed",
            "error_type": "llm_error",
        }
        result = format_sse_event("error", data)

        lines = result.strip().split("\n")
        assert lines[0] == "event: error"
        parsed = json.loads(lines[1][6:])
        assert parsed["error_message"] == "LLM generation failed"
        assert parsed["error_type"] == "llm_error"

    def test_unicode_data_preserved(self):
        """유니코드 데이터가 보존되는지 확인."""
        data = {"content": "한국어 토큰", "timestamp": _now_iso()}
        result = format_sse_event("token", data)

        lines = result.strip().split("\n")
        parsed = json.loads(lines[1][6:])
        assert parsed["content"] == "한국어 토큰"

    def test_empty_data_dict(self):
        """빈 data dict도 유효한 SSE 이벤트 생성."""
        result = format_sse_event("done", {})
        assert result == "event: done\ndata: {}\n\n"


# ---------------------------------------------------------------------------
# Unit Tests: format_heartbeat
# ---------------------------------------------------------------------------


class TestFormatHeartbeat:
    """format_heartbeat 함수 테스트."""

    def test_heartbeat_format(self):
        """하트비트 코멘트 형식이 올바른지 확인."""
        result = format_heartbeat()
        assert result == ": heartbeat\n\n"


# ---------------------------------------------------------------------------
# Unit Tests: SSEEvent model
# ---------------------------------------------------------------------------


class TestSSEEventModel:
    """SSEEvent Pydantic 모델 테스트."""

    def test_valid_event(self):
        """유효한 이벤트 생성."""
        event = SSEEvent(
            event="token",
            data={"content": "Hello"},
            timestamp="2024-01-01T00:00:00+00:00",
        )
        assert event.event == "token"
        assert event.data == {"content": "Hello"}

    def test_all_event_types(self):
        """모든 이벤트 타입이 생성 가능."""
        for event_type in VALID_EVENT_TYPES:
            event = SSEEvent(
                event=event_type,
                data={},
                timestamp=_now_iso(),
            )
            assert event.event == event_type


# ---------------------------------------------------------------------------
# Unit Tests: _classify_error
# ---------------------------------------------------------------------------


class TestClassifyError:
    """에러 분류 함수 테스트."""

    def test_timeout_error(self):
        """TimeoutError는 'timeout'으로 분류."""
        assert _classify_error(asyncio.TimeoutError()) == "timeout"

    def test_tool_related_error(self):
        """Tool 관련 에러는 'tool_error'로 분류."""

        class ToolExecutionError(Exception):
            pass

        assert _classify_error(ToolExecutionError("fail")) == "tool_error"

    def test_generic_error_defaults_to_llm_error(self):
        """일반 에러는 'llm_error'로 분류."""
        assert _classify_error(RuntimeError("something broke")) == "llm_error"
        assert _classify_error(ValueError("bad value")) == "llm_error"


# ---------------------------------------------------------------------------
# Unit Tests: stream_supervisor_response
# ---------------------------------------------------------------------------


class TestStreamSupervisorResponse:
    """stream_supervisor_response async generator 테스트."""

    @pytest.mark.asyncio
    async def test_done_event_is_last_on_success(self):
        """성공 스트림에서 done 이벤트가 마지막."""
        # Mock the LangGraph graph to emit a few events
        mock_events = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="Hello")},
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content=" world")},
            },
        ]

        mock_graph = AsyncMock()
        mock_graph.astream_events = _make_async_iter(mock_events)

        mock_service = MagicMock()
        mock_service._graph = mock_graph

        config = {"configurable": {"thread_id": "test-session"}}

        events = []
        async for event_str in stream_supervisor_response(
            service=mock_service,
            query="test query",
            config=config,
            session_id="test-session",
        ):
            events.append(event_str)

        # Last event should be "done"
        assert len(events) >= 1
        last_event = events[-1]
        assert last_event.startswith("event: done\n")

        # Parse done event data
        lines = last_event.strip().split("\n")
        parsed = json.loads(lines[1][6:])
        assert parsed["full_response"] == "Hello world"
        assert parsed["session_id"] == "test-session"
        assert parsed["tool_calls"] == []

    @pytest.mark.asyncio
    async def test_error_event_on_exception(self):
        """예외 발생 시 error 이벤트를 emit."""
        mock_graph = AsyncMock()
        mock_graph.astream_events = _make_async_iter_raising(
            RuntimeError("LLM connection failed")
        )

        mock_service = MagicMock()
        mock_service._graph = mock_graph

        config = {"configurable": {"thread_id": "test-session"}}

        events = []
        async for event_str in stream_supervisor_response(
            service=mock_service,
            query="test query",
            config=config,
            session_id="test-session",
        ):
            events.append(event_str)

        # Should have an error event
        assert len(events) >= 1
        last_event = events[-1]
        assert last_event.startswith("event: error\n")

        lines = last_event.strip().split("\n")
        parsed = json.loads(lines[1][6:])
        assert parsed["error_message"] == "LLM connection failed"
        assert parsed["error_type"] == "llm_error"

    @pytest.mark.asyncio
    async def test_token_events_have_content_and_timestamp(self):
        """token 이벤트가 content와 timestamp 필드를 포함."""
        mock_events = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="Test")},
            },
        ]

        mock_graph = AsyncMock()
        mock_graph.astream_events = _make_async_iter(mock_events)

        mock_service = MagicMock()
        mock_service._graph = mock_graph

        config = {"configurable": {"thread_id": "test-session"}}

        events = []
        async for event_str in stream_supervisor_response(
            service=mock_service,
            query="query",
            config=config,
            session_id="sess-1",
        ):
            events.append(event_str)

        # First event should be a token event
        assert len(events) >= 2  # token + done
        token_event = events[0]
        assert token_event.startswith("event: token\n")

        lines = token_event.strip().split("\n")
        parsed = json.loads(lines[1][6:])
        assert "content" in parsed
        assert parsed["content"] == "Test"
        assert "timestamp" in parsed
        # Validate timestamp is ISO 8601
        datetime.fromisoformat(parsed["timestamp"])

    @pytest.mark.asyncio
    async def test_tool_call_and_result_events(self):
        """tool_call과 tool_result 이벤트가 올바르게 생성."""
        mock_tool_output = MagicMock()
        mock_tool_output.artifact = {"formatted_sql": "SELECT 1"}

        mock_events = [
            {
                "event": "on_tool_start",
                "name": "sql_expert",
                "data": {"input": {"sub_command": "format", "sql": "select 1"}},
            },
            {
                "event": "on_tool_end",
                "name": "sql_expert",
                "data": {"output": mock_tool_output},
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="Done")},
            },
        ]

        mock_graph = AsyncMock()
        mock_graph.astream_events = _make_async_iter(mock_events)

        mock_service = MagicMock()
        mock_service._graph = mock_graph

        config = {"configurable": {"thread_id": "test-session"}}

        events = []
        async for event_str in stream_supervisor_response(
            service=mock_service,
            query="format sql",
            config=config,
            session_id="sess-1",
        ):
            events.append(event_str)

        # Should have tool_call, tool_result, token, done
        event_types = [_parse_event_type(e) for e in events]
        assert "tool_call" in event_types
        assert "tool_result" in event_types
        assert "done" in event_types

        # Validate tool_call data
        tool_call_idx = event_types.index("tool_call")
        tool_call_data = _parse_event_data(events[tool_call_idx])
        assert tool_call_data["agent_type"] == "sql_expert"
        assert tool_call_data["sub_command"] == "format"

        # Validate tool_result data
        tool_result_idx = event_types.index("tool_result")
        tool_result_data = _parse_event_data(events[tool_result_idx])
        assert tool_result_data["artifact"]["formatted_sql"] == "SELECT 1"

    @pytest.mark.asyncio
    async def test_done_event_contains_tool_calls_list(self):
        """done 이벤트에 호출된 tool 목록이 포함."""
        mock_events = [
            {
                "event": "on_tool_start",
                "name": "sql_expert",
                "data": {"input": {"sub_command": "format"}},
            },
            {
                "event": "on_tool_end",
                "name": "sql_expert",
                "data": {"output": MagicMock(artifact={})},
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="Formatted.")},
            },
        ]

        mock_graph = AsyncMock()
        mock_graph.astream_events = _make_async_iter(mock_events)

        mock_service = MagicMock()
        mock_service._graph = mock_graph

        config = {"configurable": {"thread_id": "test-session"}}

        events = []
        async for event_str in stream_supervisor_response(
            service=mock_service,
            query="format sql",
            config=config,
            session_id="sess-1",
        ):
            events.append(event_str)

        # Parse done event
        done_event = [e for e in events if e.startswith("event: done\n")]
        assert len(done_event) == 1
        done_data = _parse_event_data(done_event[0])
        assert "sql_expert" in done_data["tool_calls"]

    @pytest.mark.asyncio
    async def test_timeout_error_on_no_events(self):
        """이벤트가 60초 내에 없으면 timeout error 발생."""
        # Simulate a never-ending async iterator that hangs
        mock_graph = AsyncMock()
        mock_graph.astream_events = _make_async_iter_hanging()

        mock_service = MagicMock()
        mock_service._graph = mock_graph

        config = {"configurable": {"thread_id": "test-session"}}

        # Patch TOKEN_TIMEOUT_SECONDS to a very short value for testing
        with patch("app.framework.streaming.TOKEN_TIMEOUT_SECONDS", 0.1):
            events = []
            async for event_str in stream_supervisor_response(
                service=mock_service,
                query="test",
                config=config,
                session_id="sess-1",
            ):
                events.append(event_str)

        # Should have a timeout error event
        assert len(events) >= 1
        last_event = events[-1]
        assert last_event.startswith("event: error\n")
        parsed = _parse_event_data(last_event)
        assert parsed["error_type"] == "timeout"

    @pytest.mark.asyncio
    async def test_empty_content_chunks_are_skipped(self):
        """빈 content를 가진 chunk는 token 이벤트를 생성하지 않음."""
        mock_events = [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="")},
            },
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": MagicMock(content="Real content")},
            },
        ]

        mock_graph = AsyncMock()
        mock_graph.astream_events = _make_async_iter(mock_events)

        mock_service = MagicMock()
        mock_service._graph = mock_graph

        config = {"configurable": {"thread_id": "test-session"}}

        events = []
        async for event_str in stream_supervisor_response(
            service=mock_service,
            query="test",
            config=config,
            session_id="sess-1",
        ):
            events.append(event_str)

        # Should only have 1 token event (empty content skipped) + done
        token_events = [e for e in events if e.startswith("event: token\n")]
        assert len(token_events) == 1
        parsed = _parse_event_data(token_events[0])
        assert parsed["content"] == "Real content"


# ---------------------------------------------------------------------------
# Property-Based Tests
# ---------------------------------------------------------------------------


class TestSSEEventFormatProperty:
    """Property 18: SSE 이벤트 형식 및 순서.

    **Validates: Requirements 9.3, 9.4, 9.6, 9.7**
    """

    @given(
        event_type=st.sampled_from(list(VALID_EVENT_TYPES)),
        data=st.dictionaries(
            keys=st.text(
                alphabet=st.characters(whitelist_categories=("L", "N", "P")),
                min_size=1,
                max_size=20,
            ),
            values=st.one_of(
                st.text(max_size=100),
                st.integers(min_value=-1000, max_value=1000),
                st.booleans(),
            ),
            max_size=5,
        ),
    )
    @hypothesis_settings(max_examples=100)
    def test_sse_format_is_valid(self, event_type: str, data: dict):
        """Property: 모든 SSE 이벤트는 'event: {type}\\ndata: {json}\\n\\n' 형식.

        **Validates: Requirements 9.3**
        """
        result = format_sse_event(event_type, data)

        # Must end with double newline
        assert result.endswith("\n\n")

        # Must have exactly event and data lines
        lines = result.rstrip("\n").split("\n")
        assert len(lines) == 2
        assert lines[0] == f"event: {event_type}"
        assert lines[1].startswith("data: ")

        # Data must be valid JSON
        json_str = lines[1][6:]
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    @given(
        content=st.text(min_size=1, max_size=200),
    )
    @hypothesis_settings(max_examples=50)
    def test_token_event_has_required_fields(self, content: str):
        """Property: token 이벤트는 content와 timestamp 필드를 포함해야 함.

        **Validates: Requirements 9.4**
        """
        data = {"content": content, "timestamp": _now_iso()}
        result = format_sse_event("token", data)

        lines = result.rstrip("\n").split("\n")
        parsed = json.loads(lines[1][6:])

        assert "content" in parsed
        assert "timestamp" in parsed
        assert parsed["content"] == content
        # Timestamp should be parseable as ISO 8601
        datetime.fromisoformat(parsed["timestamp"])

    @given(
        error_msg=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
            min_size=1,
            max_size=100,
        ),
        error_type=st.sampled_from(["llm_error", "tool_error", "timeout"]),
    )
    @hypothesis_settings(max_examples=50)
    def test_error_event_has_required_fields(self, error_msg: str, error_type: str):
        """Property: error 이벤트는 error_message와 error_type을 포함해야 함.

        **Validates: Requirements 9.7**
        """
        data = {"error_message": error_msg, "error_type": error_type}
        result = format_sse_event("error", data)

        lines = result.rstrip("\n").split("\n")
        assert lines[0] == "event: error"
        parsed = json.loads(lines[1][6:])

        assert "error_message" in parsed
        assert "error_type" in parsed
        assert parsed["error_type"] in {"llm_error", "tool_error", "timeout"}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _make_async_iter(events: list):
    """이벤트 목록을 반환하는 mock astream_events 함수를 생성."""

    async def _astream_events(*args, **kwargs):
        for event in events:
            yield event

    return _astream_events


def _make_async_iter_raising(exc: Exception):
    """예외를 발생시키는 mock astream_events 함수를 생성."""

    async def _astream_events(*args, **kwargs):
        raise exc
        # Make it an async generator
        yield  # noqa: unreachable - needed to make this a generator

    return _astream_events


def _make_async_iter_hanging():
    """영원히 대기하는 mock astream_events 함수를 생성 (timeout 테스트용)."""

    async def _astream_events(*args, **kwargs):
        await asyncio.sleep(100)
        yield {}  # Never reached

    return _astream_events


def _parse_event_type(event_str: str) -> str:
    """SSE 이벤트 문자열에서 이벤트 타입을 추출."""
    first_line = event_str.split("\n")[0]
    return first_line.replace("event: ", "")


def _parse_event_data(event_str: str) -> dict:
    """SSE 이벤트 문자열에서 data JSON을 파싱."""
    lines = event_str.strip().split("\n")
    data_line = lines[1]
    return json.loads(data_line[6:])
