"""Supervisor Agent FastAPI 라우터.

프레임워크의 Supervisor Agent를 HTTP API로 노출합니다.

엔드포인트:
    POST /supervisor/chat        - Supervisor 대화 (동적 Tool Agent 활성화)
    POST /supervisor/chat/stream - SSE 스트리밍 대화
    GET  /supervisor/agents      - 등록된 Tool Agent 목록 조회
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.framework.model import create_chat_model
from app.framework.ops import ops_service
from app.framework.registry import registry
from app.framework.state_store import InMemoryStateStore, get_checkpointer
from app.framework.streaming import stream_supervisor_response
from app.framework.supervisor import SupervisorService
from app.models.schemas import (
    AgentInfo,
    AgentListResponse,
    SupervisorChatRequest,
    SupervisorChatResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/supervisor", tags=["supervisor"])

# Module-level state store for session persistence (lazy init)
_state_store: InMemoryStateStore | None = None


def _get_state_store() -> InMemoryStateStore:
    """세션 상태 저장소 인스턴스를 반환합니다 (lazy init)."""
    global _state_store
    if _state_store is None:
        try:
            settings = get_settings()
            ttl = settings.SESSION_TTL_HOURS
        except (SystemExit, Exception):
            ttl = 24
        _state_store = InMemoryStateStore(ttl_hours=ttl)
    return _state_store


def _build_tool_agents_config(request: SupervisorChatRequest) -> dict[str, dict]:
    """요청의 tool_agents 목록을 Supervisor config 형태로 변환합니다."""
    tool_agents: dict[str, dict] = {}
    for idx, ta in enumerate(request.tool_agents):
        key = ta.name or f"tool_{idx}"
        tool_agents[key] = {
            "type": ta.type,
            "name": ta.name,
            "description": ta.description,
            **ta.config,
        }
    return tool_agents


@router.get("/agents", response_model=AgentListResponse)
async def list_agents() -> AgentListResponse:
    """등록(자동 발견)된 Tool Agent 목록을 반환합니다."""
    registry.discover()
    types = registry.available_types()
    return AgentListResponse(
        agents=[AgentInfo(type=t) for t in types],
        count=len(types),
    )


@router.post("/chat", response_model=SupervisorChatResponse)
async def supervisor_chat(
    request: SupervisorChatRequest,
) -> SupervisorChatResponse:
    """Supervisor Agent와 대화합니다.

    요청에 명시된 Tool Agent들을 활성화하여 LLM이 동적으로 선택/호출합니다.
    세션 상태를 영속 저장하여 대화를 이어갈 수 있습니다.
    """
    registry.discover()
    model = create_chat_model()

    # Use get_checkpointer() for state persistence
    checkpointer, persistence_type = get_checkpointer()
    service = SupervisorService.create(model, registry, checkpointer=checkpointer)

    # Load existing state if session_id provided
    state_store = _get_state_store()
    session_id = request.session_id
    if session_id:
        existing_state = await state_store.load_state(session_id)
        if existing_state is None:
            # No stored state or expired - will start new conversation
            session_id = None

    tool_agents = _build_tool_agents_config(request)
    # AI Ops에서 비활성화한 Agent는 제외
    tool_agents = ops_service.filter_enabled(tool_agents)
    result = await service.ainvoke(
        query=request.message,
        session_id=session_id or request.session_id,
        tool_agents=tool_agents,
        system_prompt=request.system_prompt,
    )

    # Save state after graph invocation
    result_session_id = result["session_id"]
    try:
        state_to_save = {
            "response": result["response"],
            "session_id": result_session_id,
            "sources": result["sources"],
            "tool_calls": result["tool_calls"],
        }
        await state_store.save_state(result_session_id, state_to_save)
    except Exception as e:
        logger.warning("Failed to save session state: %s", str(e))

    response = SupervisorChatResponse(
        response=result["response"],
        session_id=result_session_id,
        sources=result["sources"],
        tool_calls=result["tool_calls"],
    )

    # Add persistence type info if using fallback
    if persistence_type == "in_memory":
        logger.warning(
            "State persistence is using in-memory fallback for session %s",
            result_session_id,
        )

    return response


@router.post(
    "/chat/stream",
    summary="Supervisor SSE 스트리밍 대화",
    description="Supervisor Agent와 SSE(Server-Sent Events) 스트리밍 대화를 수행합니다. "
    "토큰 단위로 실시간 이벤트를 전달하며, tool_call/tool_result 이벤트도 포함됩니다.",
    responses={
        200: {
            "description": "text/event-stream SSE 응답",
            "content": {"text/event-stream": {}},
        },
    },
)
async def supervisor_chat_stream(
    request: SupervisorChatRequest,
    raw_request: Request,
) -> StreamingResponse:
    """Supervisor Agent와 SSE 스트리밍 대화를 수행합니다.

    동일한 요청 본문을 받아 text/event-stream으로 토큰별 SSE 이벤트를 반환합니다.
    LangGraph의 astream_events를 사용하여 실시간 토큰 스트리밍을 제공합니다.

    이벤트 타입:
        - token: LLM 토큰 생성 {"content": str, "timestamp": ISO8601}
        - tool_call: Tool 호출 시작 {"agent_type": str, "sub_command": str, "timestamp": str}
        - tool_result: Tool 결과 {"artifact": dict, "timestamp": str}
        - done: 완료 {"full_response": str, "session_id": str, "tool_calls": list}
        - error: 에러 {"error_message": str, "error_type": str}
    """
    registry.discover()
    model = create_chat_model()
    service = SupervisorService.create(model, registry)

    tool_agents = _build_tool_agents_config(request)
    tool_agents = ops_service.filter_enabled(tool_agents)

    session_id = request.session_id or str(uuid.uuid4())
    config = service.build_config(
        session_id=session_id,
        tool_agents=tool_agents,
        system_prompt=request.system_prompt,
    )

    async def event_generator():
        """클라이언트 연결 상태를 확인하며 SSE 이벤트를 생성합니다."""
        async for event_str in stream_supervisor_response(
            service=service,
            query=request.message,
            config=config,
            session_id=session_id,
        ):
            # Check if client disconnected
            if await raw_request.is_disconnected():
                logger.info(
                    "Client disconnected during stream, session=%s", session_id
                )
                break
            yield event_str

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
