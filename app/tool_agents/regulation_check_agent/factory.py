"""Regulation Check Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.regulation_check_agent.tool import AGENT_TYPE, RegulationCheckTool


class RegulationCheckFactory(BaseToolFactory):
    """RegulationCheckTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE
    display_name = "규정 확인"
    category = "Compliance"
    complexity = "medium"
    summary = "규정 관련 질문에 대해 관련 조항, 적용 범위, 주의사항을 정리하여 답변합니다"
    tags = ("regulation", "compliance", "policy")

    def create_tool(self, tool_config: dict[str, Any]) -> RegulationCheckTool:
        return RegulationCheckTool(
            name=tool_config.get("name", "regulation_check"),
            description=tool_config.get(
                "description",
                "규정 관련 질문에 대해 관련 조항, 적용 범위, 주의사항을 정리하여 답변합니다. "
                "질문과 카테고리를 입력하면 관련 규정과 면책조항을 포함한 답변을 반환합니다.",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- regulation_check: 규정이나 내규에 대해 확인할 때 사용합니다. "
            "질문과 카테고리(hr/finance/security/procurement/general)를 입력하면 "
            "관련 규정 조항, 주의사항, 면책조항을 포함한 답변을 제공합니다."
        )


def get_factory() -> RegulationCheckFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return RegulationCheckFactory()
