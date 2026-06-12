"""Supervisor Agent FastAPI 라우터.

프레임워크의 Supervisor Agent를 HTTP API로 노출합니다.

엔드포인트:
    POST /supervisor/chat   - Supervisor 대화 (동적 Tool Agent 활성화)
    GET  /supervisor/agents - 등록된 Tool Agent 목록 조회
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.framework.model import create_chat_model
from app.framework.ops import ops_service
from app.framework.registry import registry
from app.framework.supervisor import SupervisorService
from app.models.schemas import (
    AgentInfo,
    AgentListResponse,
    SupervisorChatRequest,
    SupervisorChatResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/supervisor", tags=["supervisor"])


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
    """
    registry.discover()
    model = create_chat_model()
    service = SupervisorService.create(model, registry)

    tool_agents = _build_tool_agents_config(request)
    # AI Ops에서 비활성화한 Agent는 제외
    tool_agents = ops_service.filter_enabled(tool_agents)
    result = await service.ainvoke(
        query=request.message,
        session_id=request.session_id,
        tool_agents=tool_agents,
        system_prompt=request.system_prompt,
    )

    return SupervisorChatResponse(
        response=result["response"],
        session_id=result["session_id"],
        sources=result["sources"],
        tool_calls=result["tool_calls"],
    )
