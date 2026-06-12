"""Pydantic 스키마 - API 요청/응답 모델 정의.

이 모듈은 Agent_Server의 HTTP API 요청/응답에 사용되는 Pydantic 모델을
정의합니다. FastAPI가 이 모델들을 사용해 요청 검증, 응답 직렬화,
Swagger UI(/docs) 문서를 자동 생성합니다.

Requirements: 2.4 (헬스체크 JSON 응답), 2.5 (에러 응답)
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Agent 대화 요청 모델.

    클라이언트가 ``POST /agent/chat`` 으로 전송하는 요청 본문입니다.
    """

    message: str = Field(
        ...,
        min_length=1,
        description="사용자가 Agent에게 전달하는 메시지",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="대화 세션 식별자. 미지정 시 서버가 새 세션을 생성한다.",
    )


class UsageMetadata(BaseModel):
    """LLM 사용량 메타데이터.

    단일 LLM 호출에 대한 토큰 사용량, 소요 시간, 비용 추정값을 담는다.
    """

    prompt_tokens: int = Field(
        ...,
        ge=0,
        description="프롬프트(입력)에 사용된 토큰 수",
    )
    completion_tokens: int = Field(
        ...,
        ge=0,
        description="응답(출력)에 사용된 토큰 수",
    )
    total_tokens: int = Field(
        ...,
        ge=0,
        description="총 토큰 수 (prompt_tokens + completion_tokens)",
    )
    duration_ms: float = Field(
        ...,
        ge=0,
        description="LLM 호출 소요 시간 (밀리초)",
    )
    estimated_cost_usd: float = Field(
        ...,
        ge=0,
        description="추정 비용 (USD, 소수점 6자리까지)",
    )


class ChatResponse(BaseModel):
    """Agent 대화 응답 모델.

    ``POST /agent/chat`` 의 응답 본문입니다.
    """

    response: str = Field(
        ...,
        description="Agent가 생성한 응답 텍스트",
    )
    session_id: str = Field(
        ...,
        description="요청을 처리한 대화 세션 식별자",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="RAG 검색으로 참고한 문서 출처 목록",
    )
    usage: Optional[UsageMetadata] = Field(
        default=None,
        description="LLM 사용량 메타데이터 (가용한 경우)",
    )


class HealthResponse(BaseModel):
    """헬스체크 응답 모델.

    ``GET /health`` 의 응답 본문입니다.
    """

    status: str = Field(
        ...,
        description='전체 서비스 상태: "healthy" | "degraded" | "unhealthy"',
    )
    database: str = Field(
        ...,
        description='Database 연결 상태: "connected" | "disconnected"',
    )
    elasticsearch: str = Field(
        ...,
        description='Elasticsearch 연결 상태: "connected" | "disconnected"',
    )
    uptime_seconds: float = Field(
        ...,
        ge=0,
        description="서버 기동 후 경과 시간 (초)",
    )


class ToolAgentConfig(BaseModel):
    """Supervisor에 활성화할 단일 Tool Agent 설정."""

    type: str = Field(..., description="Tool Agent 타입 식별자 (예: 'calculator_agent')")
    name: str = Field(..., description="LLM에 노출될 Tool 이름")
    description: str = Field(
        default="", description="LLM이 Tool 선택에 참고할 설명"
    )
    config: dict = Field(
        default_factory=dict,
        description="Tool Agent별 추가 설정 (예: index, top_k 등)",
    )


class SupervisorChatRequest(BaseModel):
    """Supervisor Agent 대화 요청 모델."""

    message: str = Field(..., min_length=1, description="사용자 메시지")
    session_id: Optional[str] = Field(
        default=None, description="대화 세션 식별자. 미지정 시 서버가 생성."
    )
    tool_agents: list[ToolAgentConfig] = Field(
        default_factory=list,
        description="활성화할 Tool Agent 목록. 비우면 LLM이 직접 답변.",
    )
    system_prompt: Optional[str] = Field(
        default=None, description="시스템 프롬프트 재정의 (선택)"
    )


class SupervisorChatResponse(BaseModel):
    """Supervisor Agent 대화 응답 모델."""

    response: str = Field(..., description="최종 응답 텍스트")
    session_id: str = Field(..., description="대화 세션 식별자")
    sources: list[str] = Field(
        default_factory=list, description="참고한 문서 출처 목록"
    )
    tool_calls: list[str] = Field(
        default_factory=list, description="실행된 Tool 이름 목록"
    )


class AgentInfo(BaseModel):
    """등록된 Tool Agent 정보."""

    type: str = Field(..., description="Tool Agent 타입 식별자")


class AgentListResponse(BaseModel):
    """사용 가능한 Tool Agent 목록 응답."""

    agents: list[AgentInfo] = Field(
        default_factory=list, description="등록된 Tool Agent 목록"
    )
    count: int = Field(..., ge=0, description="등록된 Tool Agent 수")


class ErrorResponse(BaseModel):
    """에러 응답 모델.

    처리되지 않은 예외 등으로 인한 에러 응답 본문입니다.
    """

    error: str = Field(
        ...,
        description='에러 유형 (예: "connection_error", "validation_error")',
    )
    message: str = Field(
        ...,
        description="사용자 친화적 에러 메시지",
    )
    detail: Optional[str] = Field(
        default=None,
        description="상세 정보 (DEBUG 모드에서만 노출)",
    )
    request_id: str = Field(
        ...,
        description="요청 추적용 ID",
    )
