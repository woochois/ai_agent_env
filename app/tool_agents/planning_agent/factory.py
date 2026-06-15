"""Planning Agent 팩토리.

Requirements: 5.1, 5.7 (deprecated flags on original factories)
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.planning_agent.tool import AGENT_TYPE, PlanningTool


class PlanningFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "Planning Expert"
    category = "Planning"
    complexity = "medium"
    summary = (
        "프로젝트 WBS 분해와 일정 계획을 통합 제공하는 전문 에이전트입니다."
    )
    tags = ("planning", "wbs", "schedule", "project")
    requires = ()
    deprecated = False

    def create_tool(self, tool_config: dict[str, Any]) -> PlanningTool:
        return PlanningTool(
            name=tool_config.get("name", "planning"),
            description=tool_config.get(
                "description",
                "계획 관련 작업을 통합 제공합니다 (breakdown_task, plan_schedule).",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- planning: 프로젝트 WBS 분해(breakdown_task), "
            "일정 계획(plan_schedule)을 수행합니다. "
            "sub_command 파라미터로 기능을 선택합니다."
        )


def get_factory() -> PlanningFactory:
    return PlanningFactory()
