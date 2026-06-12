"""Presentation Helper Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.presentation_helper_agent.tool import AGENT_TYPE, PresentationHelperTool


class PresentationHelperFactory(BaseToolFactory):
    """PresentationHelperTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE
    display_name = "발표 자료 도우미"
    category = "Communication"
    complexity = "medium"
    summary = "발표 자료의 슬라이드 구성과 각 슬라이드별 스크립트를 생성합니다"
    tags = ("presentation", "slides", "script")

    def create_tool(self, tool_config: dict[str, Any]) -> PresentationHelperTool:
        return PresentationHelperTool(
            name=tool_config.get("name", "presentation_helper"),
            description=tool_config.get(
                "description",
                "발표 자료의 슬라이드 구성과 스크립트를 생성합니다. "
                "발표 주제, 대상 청중, 발표 시간을 입력하면 슬라이드별 구성과 스크립트를 반환합니다.",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- presentation_helper: 발표 자료를 구성할 때 사용합니다. "
            "주제, 청중, 발표 시간을 입력하면 슬라이드 구성과 발표 스크립트를 생성합니다."
        )


def get_factory() -> PresentationHelperFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return PresentationHelperFactory()
