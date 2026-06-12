"""Meeting Summary Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.meeting_summary_agent.tool import AGENT_TYPE, MeetingSummaryTool


class MeetingSummaryFactory(BaseToolFactory):
    """MeetingSummaryTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE
    display_name = "회의록 요약"
    category = "Productivity"
    complexity = "simple"
    summary = "회의 내용을 입력하면 참석자, 안건, 결정사항, 액션아이템으로 구조화된 요약을 생성합니다"
    tags = ("meeting", "summary", "minutes")

    def create_tool(self, tool_config: dict[str, Any]) -> MeetingSummaryTool:
        return MeetingSummaryTool(
            name=tool_config.get("name", "meeting_summary"),
            description=tool_config.get(
                "description",
                "회의 내용을 구조화된 요약으로 변환합니다. "
                "참석자, 안건, 결정사항, 액션아이템을 추출하여 정리합니다.",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- meeting_summary: 회의 내용을 구조화된 요약으로 정리할 때 사용합니다. "
            "회의 내용을 입력하면 참석자, 안건, 결정사항, 액션아이템을 추출합니다."
        )


def get_factory() -> MeetingSummaryFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return MeetingSummaryFactory()
