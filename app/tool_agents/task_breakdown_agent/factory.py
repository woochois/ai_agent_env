"""Task Breakdown Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.task_breakdown_agent.tool import AGENT_TYPE, TaskBreakdownTool


class TaskBreakdownFactory(BaseToolFactory):
    """TaskBreakdownTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE
    display_name = "업무 분해"
    category = "Project Management"
    complexity = "medium"
    summary = "프로젝트를 WBS로 분해하여 태스크 목록, 의존관계, 소요시간을 추정합니다"
    tags = ("project", "wbs", "planning")
    deprecated = True

    def create_tool(self, tool_config: dict[str, Any]) -> TaskBreakdownTool:
        return TaskBreakdownTool(
            name=tool_config.get("name", "task_breakdown"),
            description=tool_config.get(
                "description",
                "프로젝트를 WBS로 분해하여 태스크 목록, 의존관계, 소요시간을 추정합니다. "
                "프로젝트 설명과 목표를 입력하면 구조화된 업무 분해 결과를 반환합니다.",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- task_breakdown: 프로젝트를 업무 단위로 분해할 때 사용합니다. "
            "프로젝트 설명과 목표를 입력하면 WBS, 의존관계, 소요시간을 추정합니다."
        )


def get_factory() -> TaskBreakdownFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return TaskBreakdownFactory()
