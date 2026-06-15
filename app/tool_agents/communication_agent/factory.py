"""Communication Agent 팩토리.

Requirements: 3.1, 3.10
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.communication_agent.tool import AGENT_TYPE, CommunicationTool


class CommunicationFactory(BaseToolFactory):
    """CommunicationTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE
    display_name = "Communication"
    category = "Communication"
    complexity = "medium"
    summary = (
        "이메일 초안 작성, 번역, 회의록 요약을 통합 제공하는 커뮤니케이션 에이전트입니다."
    )
    tags = ("email", "translation", "meeting", "communication")
    deprecated = False

    def create_tool(self, tool_config: dict[str, Any]) -> CommunicationTool:
        return CommunicationTool(
            name=tool_config.get("name", "communication"),
            description=tool_config.get(
                "description",
                "커뮤니케이션 관련 작업을 통합 제공합니다 (draft_email, translate, summarize_meeting).",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- communication: 이메일 초안 작성(draft_email), 번역(translate), "
            "회의록 요약(summarize_meeting)을 수행합니다. "
            "sub_command 파라미터로 기능을 선택합니다."
        )


def get_factory() -> CommunicationFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return CommunicationFactory()
