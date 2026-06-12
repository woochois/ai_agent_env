"""AI Agent 프레임워크 코어.

이 패키지는 AI Agent를 빠르게 양산하기 위한 기본 틀을 제공합니다.
klid-aicb의 플러그인 + 팩토리 + LangGraph Supervisor 패턴을 참고하여,
다음을 핵심 가치로 설계되었습니다.

1. **플러그인 아키텍처**: 각 Tool Agent는 독립 패키지(`app/tool_agents/<name>/`)로
   존재하며, 폴더만 추가하면 자동으로 등록됩니다 (auto-discovery).
2. **팩토리 패턴**: `BaseToolFactory`가 런타임 config로부터 Tool을 동적 생성합니다.
3. **LangGraph Supervisor**: ReAct 루프(agent ⟷ tools)로 여러 Tool Agent를
   오케스트레이션합니다.
4. **표준 Artifact**: 모든 Tool은 `(content, artifact)` 형태로 결과를 반환하며,
   `auto_error_artifact` 데코레이터로 에러를 일관되게 처리합니다.

주요 export:
    BaseAgentTool, BaseToolFactory, auto_error_artifact - Tool Agent 작성용 기반
    ToolAgentRegistry, DynamicToolFactory - 등록 및 동적 생성
    build_artifact, build_error_artifact - Artifact 헬퍼
"""

from app.framework.base import (
    BaseAgentTool,
    BaseToolFactory,
    auto_error_artifact,
    build_artifact,
    build_error_artifact,
)
from app.framework.registry import DynamicToolFactory, ToolAgentRegistry, registry

__all__ = [
    "BaseAgentTool",
    "BaseToolFactory",
    "auto_error_artifact",
    "build_artifact",
    "build_error_artifact",
    "DynamicToolFactory",
    "ToolAgentRegistry",
    "registry",
]
