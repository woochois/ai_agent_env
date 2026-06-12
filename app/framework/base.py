"""Tool Agent 작성을 위한 기반 클래스 및 유틸리티.

새로운 AI Agent를 만들 때 상속/사용하는 핵심 빌딩 블록입니다.

- ``BaseAgentTool``: LangChain ``BaseTool``을 확장한 Tool Agent 진입점.
- ``BaseToolFactory``: config로부터 Tool을 동적 생성하는 팩토리 인터페이스.
- ``auto_error_artifact``: Tool 실행 중 예외를 표준 error artifact로 변환하는 데코레이터.
- ``build_artifact`` / ``build_error_artifact``: 표준 artifact 생성 헬퍼.

설계 참고: klid-aicb의 ``tool_agents/base.py`` 패턴.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from app.framework.manifest import AgentManifest
from app.framework.metrics import metrics

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Artifact 헬퍼
# ---------------------------------------------------------------------------
#
# 모든 Tool Agent는 결과를 표준 artifact(JSON 직렬화 가능한 dict)로 반환합니다.
# 필수 필드: "type" (Tool Agent 식별자)
# 에러 필드: "error_message", "error_detail" (실패 시)
#


def build_artifact(agent_type: str, **fields: Any) -> dict[str, Any]:
    """성공 artifact를 생성합니다.

    Args:
        agent_type: Tool Agent 타입 식별자 (예: "rag_search_agent").
        **fields: artifact에 포함할 추가 데이터 필드.

    Returns:
        ``{"type": agent_type, ...fields}`` 형태의 딕셔너리.
    """
    return {"type": agent_type, **fields}


def build_error_artifact(
    agent_type: str,
    error_message: str,
    error_detail: str = "",
    **fields: Any,
) -> dict[str, Any]:
    """에러 artifact를 생성합니다.

    Args:
        agent_type: Tool Agent 타입 식별자.
        error_message: 사용자 친화적 에러 메시지.
        error_detail: 디버깅용 상세 에러 내용.
        **fields: artifact에 포함할 추가 기본 필드.

    Returns:
        에러 정보를 포함한 artifact 딕셔너리.
    """
    return {
        "type": agent_type,
        "error_message": error_message,
        "error_detail": error_detail,
        **fields,
    }


# ---------------------------------------------------------------------------
# auto_error_artifact 데코레이터
# ---------------------------------------------------------------------------


def auto_error_artifact(
    agent_type: str,
    default_message: str | None = None,
    **default_fields: Any,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Tool 실행 중 발생한 모든 예외를 표준 error artifact로 변환하는 데코레이터.

    ``BaseAgentTool``의 ``_run`` / ``_arun`` 메서드에 적용합니다. 동기/비동기
    함수를 모두 지원하며, 예외 발생 시 ``("", error_artifact)`` 튜플을 반환하여
    Tool 호출이 중단되지 않고 LLM이 에러를 인지할 수 있게 합니다.

    Args:
        agent_type: Tool Agent 타입 식별자.
        default_message: 기본 에러 메시지. None이면 agent_type으로 자동 생성.
        **default_fields: error artifact에 포함할 추가 기본 필드.

    Returns:
        데코레이터 함수.
    """

    def _fallback_message() -> str:
        return default_message or (
            f"{agent_type.replace('_', ' ').title()} 실행 중 오류가 발생했습니다"
        )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> tuple[str, dict]:
            _validate_self(args)
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)  # type: ignore[misc]
                metrics.record(
                    agent_type,
                    success=True,
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                )
                return result
            except Exception as exc:  # noqa: BLE001 - 모든 예외를 artifact로 변환
                metrics.record(
                    agent_type,
                    success=False,
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                    error=str(exc),
                )
                logger.warning(
                    "Tool '%s' 실행 실패: %s",
                    agent_type,
                    exc,
                    extra={"agent_type": agent_type, "error": str(exc)},
                )
                return "", build_error_artifact(
                    agent_type, _fallback_message(), str(exc), **default_fields
                )

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> tuple[str, dict]:
            _validate_self(args)
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)  # type: ignore[return-value]
                metrics.record(
                    agent_type,
                    success=True,
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                )
                return result
            except Exception as exc:  # noqa: BLE001
                metrics.record(
                    agent_type,
                    success=False,
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                    error=str(exc),
                )
                logger.warning(
                    "Tool '%s' 실행 실패: %s",
                    agent_type,
                    exc,
                    extra={"agent_type": agent_type, "error": str(exc)},
                )
                return "", build_error_artifact(
                    agent_type, _fallback_message(), str(exc), **default_fields
                )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


def _validate_self(args: tuple[Any, ...]) -> None:
    """데코레이터가 BaseTool 메서드에 적용되었는지 검증합니다."""
    self_instance = args[0] if args else None
    if not isinstance(self_instance, BaseTool):
        raise TypeError(
            "auto_error_artifact 데코레이터는 BaseTool의 메서드에만 사용 가능합니다"
        )


# ---------------------------------------------------------------------------
# 기반 클래스
# ---------------------------------------------------------------------------


class BaseAgentTool(BaseTool):
    """Tool Agent의 진입점이 되는 기반 Tool 클래스.

    LangChain ``BaseTool``을 확장합니다. 모든 Tool Agent는 이 클래스를 상속하고
    ``_arun`` (비동기 실행)을 구현해야 합니다. ``_arun``은 ``(content, artifact)``
    튜플을 반환하며, ``auto_error_artifact`` 데코레이터를 함께 사용하는 것을 권장합니다.

    ``format_content``를 오버라이드하면 artifact를 LLM에게 전달할 텍스트(보통 마크다운)로
    변환할 수 있습니다.
    """

    def format_content(self, message: ToolMessage) -> ToolMessage:
        """artifact를 LLM에게 전달하기 위한 형식으로 변환합니다.

        기본 구현은 메시지를 그대로 반환합니다. Tool Agent는 필요 시
        artifact를 사람이 읽기 좋은 텍스트로 변환하도록 오버라이드합니다.

        Args:
            message: Tool 실행 결과 ToolMessage.

        Returns:
            LLM 전달용으로 가공된 ToolMessage.
        """
        return message


class BaseToolFactory(ABC):
    """Tool Agent를 동적으로 생성하는 팩토리 인터페이스.

    각 Tool Agent 패키지는 이 클래스를 상속한 팩토리를 제공하고,
    패키지의 ``factory.py``에서 ``get_factory()``로 인스턴스를 노출합니다.
    레지스트리가 이를 자동 수집합니다.

    AI Ops를 위한 메타데이터(category, complexity 등)를 클래스 속성으로 선언하면,
    Ops 레이어가 에이전트를 카탈로그화/분류합니다.
    """

    #: 이 팩토리가 생성하는 Tool Agent의 타입 식별자. 하위 클래스에서 반드시 지정.
    agent_type: str = ""

    # --- AI Ops 메타데이터 (하위 클래스에서 선택적으로 재정의) ---
    #: 사람이 읽는 표시 이름. 비우면 agent_type에서 자동 생성.
    display_name: str = ""
    #: 분류 (예: "SQL", "Schema", "Performance", "Data Quality").
    category: str = "General"
    #: 난이도 ("simple" | "medium" | "advanced").
    complexity: str = "simple"
    #: 한 줄 요약.
    summary: str = ""
    #: 검색/필터용 태그.
    tags: tuple[str, ...] = ()
    #: 외부 의존성 (예: ("postgresql",)). 비어 있으면 순수 로직.
    requires: tuple[str, ...] = ()
    #: 에이전트 버전.
    version: str = "1.0.0"

    def is_target_tool(self, tool_type: str) -> bool:
        """주어진 tool_type을 이 팩토리가 생성할 수 있는지 판단합니다.

        기본 구현은 ``agent_type``과 일치하는지 비교합니다.
        """
        return tool_type == self.agent_type

    def get_manifest(self) -> AgentManifest:
        """이 Agent의 매니페스트(메타데이터)를 반환합니다.

        클래스 속성으로부터 매니페스트를 구성합니다. 필요 시 오버라이드 가능합니다.
        """
        display = self.display_name or self.agent_type.replace("_", " ").title()
        return AgentManifest(
            agent_type=self.agent_type,
            display_name=display,
            category=self.category,
            complexity=self.complexity,
            summary=self.summary,
            tags=tuple(self.tags),
            requires=tuple(self.requires),
            version=self.version,
        )

    @abstractmethod
    def create_tool(self, tool_config: dict[str, Any]) -> BaseAgentTool:
        """tool_config를 기반으로 Tool 인스턴스를 생성합니다.

        Args:
            tool_config: ``{"type", "name", "description", ...}`` 형태의 설정.

        Returns:
            생성된 BaseAgentTool 인스턴스.
        """

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        """Supervisor에게 전달할 이 Tool의 사용법 프롬프트를 생성합니다.

        기본 구현은 빈 문자열을 반환합니다. Tool Agent는 필요 시
        사용 조건/예시를 담은 프롬프트를 반환하도록 오버라이드합니다.
        """
        return ""
