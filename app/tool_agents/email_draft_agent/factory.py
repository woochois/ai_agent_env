"""Email Draft Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.email_draft_agent.tool import AGENT_TYPE, EmailDraftTool


class EmailDraftFactory(BaseToolFactory):
    """EmailDraftTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE
    display_name = "이메일 초안 작성"
    category = "Communication"
    complexity = "simple"
    summary = "목적, 수신자, 핵심내용을 입력하면 비즈니스 이메일 초안을 생성합니다"
    tags = ("email", "draft", "writing")

    def create_tool(self, tool_config: dict[str, Any]) -> EmailDraftTool:
        return EmailDraftTool(
            name=tool_config.get("name", "email_draft"),
            description=tool_config.get(
                "description",
                "비즈니스 이메일 초안을 작성합니다. "
                "목적, 수신자, 핵심 전달 내용을 입력하면 적절한 톤과 구조의 이메일을 생성합니다.",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- email_draft: 비즈니스 이메일 초안이 필요할 때 사용합니다. "
            "목적, 수신자, 핵심내용을 입력하면 적절한 톤과 구조의 이메일을 생성합니다."
        )


def get_factory() -> EmailDraftFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return EmailDraftFactory()
