"""SSE (Server-Sent Events) 스트리밍 유틸리티.

LangGraph의 astream_events를 SSE 형식으로 변환하여 클라이언트에게
실시간으로 토큰을 전달합니다.

SSE 이벤트 형식:
    event: {event_type}
    data: {json_payload}

이벤트 타입:
    - token: LLM 토큰 생성
    - tool_call: Tool Agent 호출 시작
    - tool_result: Tool Agent 호출 완료
    - done: 스트림 완료
    - error: 에러 발생

Requirements: 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, AsyncGenerator

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.framework.supervisor import SupervisorService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEARTBEAT_INTERVAL_SECONDS = 15
TOKEN_TIMEOUT_SECONDS = 60
VALID_EVENT_TYPES = {"token", "tool_call", "tool_result", "done", "error"}


# ---------------------------------------------------------------------------
# SSE Event Model
# ---------------------------------------------------------------------------


class SSEEvent(BaseModel):
    """SSE 이벤트 데이터 모델."""

    event: str  # "token" | "tool_call" | "tool_result" | "done" | "error"
    data: dict
    timestamp: str


# ---------------------------------------------------------------------------
# SSE Formatting
# ---------------------------------------------------------------------------


def format_sse_event(event_type: str, data: dict) -> str:
    """단일 SSE 이벤트 문자열을 포맷합니다.

    Args:
        event_type: 이벤트 타입 (token, tool_call, tool_result, done, error).
        data: JSON 직렬화 가능한 데이터 딕셔너리.

    Returns:
        "event: {type}\\ndata: {json}\\n\\n" 형식의 문자열.
    """
    json_payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_payload}\n\n"


def format_heartbeat() -> str:
    """하트비트 코멘트 라인을 반환합니다.

    Returns:
        ": heartbeat\\n\\n" 형식의 SSE 코멘트.
    """
    return ": heartbeat\n\n"


def _now_iso() -> str:
    """현재 시간을 ISO 8601 형식으로 반환합니다."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Stream Supervisor Response
# ---------------------------------------------------------------------------


async def stream_supervisor_response(
    service: Any,
    query: str,
    config: dict,
    session_id: str,
) -> AsyncGenerator[str, None]:
    """LangGraph astream_events를 SSE 형식으로 변환하여 yield합니다.

    LangGraph 이벤트를 다음과 같이 매핑합니다:
        - on_chat_model_stream → "token" 이벤트
        - on_tool_start → "tool_call" 이벤트
        - on_tool_end → "tool_result" 이벤트

    스트림 완료 시 "done" 이벤트를, 에러 발생 시 "error" 이벤트를 emit합니다.

    Args:
        service: SupervisorService 인스턴스.
        query: 사용자 질의.
        config: LangGraph 실행 설정 (configurable 포함).
        session_id: 대화 세션 ID.

    Yields:
        SSE 형식의 문자열.
    """
    from langchain_core.messages import HumanMessage

    full_response = ""
    tool_calls: list[str] = []
    last_event_time = asyncio.get_event_loop().time()

    try:
        graph = service._graph

        async def _event_stream():
            nonlocal full_response, tool_calls, last_event_time

            async for event in graph.astream_events(
                {"query": query, "messages": [HumanMessage(content=query)], "data": {}},
                config=config,
                version="v2",
            ):
                last_event_time = asyncio.get_event_loop().time()
                kind = event.get("event", "")

                if kind == "on_chat_model_stream":
                    # Token event
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        content = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                        full_response += content
                        yield format_sse_event("token", {
                            "content": content,
                            "timestamp": _now_iso(),
                        })

                elif kind == "on_tool_start":
                    # Tool call event
                    name = event.get("name", "")
                    metadata = event.get("data", {}).get("input", {})
                    sub_command = ""
                    if isinstance(metadata, dict):
                        sub_command = metadata.get("sub_command", "")
                    tool_calls.append(name)
                    yield format_sse_event("tool_call", {
                        "agent_type": name,
                        "sub_command": sub_command,
                        "timestamp": _now_iso(),
                    })

                elif kind == "on_tool_end":
                    # Tool result event
                    output = event.get("data", {}).get("output")
                    artifact = {}
                    if output and hasattr(output, "artifact"):
                        artifact = output.artifact if isinstance(output.artifact, dict) else {}
                    elif isinstance(output, dict):
                        artifact = output
                    yield format_sse_event("tool_result", {
                        "artifact": artifact,
                        "timestamp": _now_iso(),
                    })

        # Use heartbeat and timeout logic
        event_gen = _event_stream()
        while True:
            try:
                sse_str = await asyncio.wait_for(
                    event_gen.__anext__(),
                    timeout=TOKEN_TIMEOUT_SECONDS,
                )
                yield sse_str
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                # Token timeout - emit error event
                yield format_sse_event("error", {
                    "error_message": "Token generation timed out after 60 seconds",
                    "error_type": "timeout",
                })
                return

        # Stream completed successfully - emit done event
        yield format_sse_event("done", {
            "full_response": full_response,
            "session_id": session_id,
            "tool_calls": tool_calls,
        })

    except asyncio.CancelledError:
        # Client disconnected
        logger.info("Client disconnected, terminating stream for session %s", session_id)
        return
    except Exception as exc:
        # Determine error type
        error_type = _classify_error(exc)
        error_message = str(exc) if str(exc) else type(exc).__name__

        # Sanitize: don't expose stack traces
        if "\n" in error_message:
            error_message = error_message.split("\n")[0]

        yield format_sse_event("error", {
            "error_message": error_message,
            "error_type": error_type,
        })


def _classify_error(exc: Exception) -> str:
    """예외 유형에 따라 error_type을 분류합니다.

    Args:
        exc: 발생한 예외.

    Returns:
        "llm_error", "tool_error", 또는 "timeout" 중 하나.
    """
    exc_type_name = type(exc).__name__.lower()

    if isinstance(exc, asyncio.TimeoutError) or "timeout" in exc_type_name:
        return "timeout"
    if "tool" in exc_type_name:
        return "tool_error"
    # Default to llm_error for LLM-related issues
    return "llm_error"
