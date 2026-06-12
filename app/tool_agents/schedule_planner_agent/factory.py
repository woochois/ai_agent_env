"""Schedule Planner Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.schedule_planner_agent.tool import AGENT_TYPE, SchedulePlannerTool


class SchedulePlannerFactory(BaseToolFactory):
    """SchedulePlannerTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE
    display_name = "일정 계획"
    category = "Productivity"
    complexity = "medium"
    summary = "업무 목록과 마감일을 입력하면 우선순위와 일별 일정 제안을 생성합니다"
    tags = ("schedule", "planning", "priority")

    def create_tool(self, tool_config: dict[str, Any]) -> SchedulePlannerTool:
        return SchedulePlannerTool(
            name=tool_config.get("name", "schedule_planner"),
            description=tool_config.get(
                "description",
                "업무 목록과 마감일을 입력하면 우선순위와 일별 일정 제안을 생성합니다. "
                "업무명, 소요시간, 마감일을 포함한 텍스트를 입력하세요.",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- schedule_planner: 일정 계획이 필요할 때 사용합니다. "
            "업무 목록과 마감일을 입력하면 우선순위와 일별 일정 제안을 생성합니다."
        )


def get_factory() -> SchedulePlannerFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return SchedulePlannerFactory()
