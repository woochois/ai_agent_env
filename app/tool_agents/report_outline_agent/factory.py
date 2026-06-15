"""Report Outline Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.report_outline_agent.tool import AGENT_TYPE, ReportOutlineTool


class ReportOutlineFactory(BaseToolFactory):
    """ReportOutlineTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE
    display_name = "보고서 개요 작성"
    category = "Documentation"
    complexity = "simple"
    summary = "주제와 목적을 입력하면 보고서 목차와 섹션별 요점을 제안합니다"
    tags = ("report", "outline", "writing")
    deprecated = True

    def create_tool(self, tool_config: dict[str, Any]) -> ReportOutlineTool:
        return ReportOutlineTool(
            name=tool_config.get("name", "report_outline"),
            description=tool_config.get(
                "description",
                "보고서 개요를 작성합니다. "
                "주제, 목적, 대상 독자를 입력하면 목차와 섹션별 요점을 제안합니다.",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- report_outline: 보고서 개요가 필요할 때 사용합니다. "
            "주제, 목적, 대상 독자를 입력하면 목차와 섹션별 요점을 제안합니다."
        )


def get_factory() -> ReportOutlineFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return ReportOutlineFactory()
