"""Translation Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.translation_agent.tool import AGENT_TYPE, TranslationTool


class TranslationFactory(BaseToolFactory):
    """TranslationTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE
    display_name = "비즈니스 번역"
    category = "Communication"
    complexity = "medium"
    summary = "비즈니스 문서를 한↔영 번역하며 전문 용어 일관성과 비즈니스 톤을 유지합니다"
    tags = ("translation", "korean", "english")
    deprecated = True

    def create_tool(self, tool_config: dict[str, Any]) -> TranslationTool:
        return TranslationTool(
            name=tool_config.get("name", "translation"),
            description=tool_config.get(
                "description",
                "비즈니스 문서를 한↔영 번역합니다. "
                "원문 언어를 자동 감지하고 도메인 전문 용어를 반영하여 비즈니스 톤을 유지합니다.",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- translation: 비즈니스 문서의 한↔영 번역이 필요할 때 사용합니다. "
            "원문 언어를 자동 감지하고 도메인 전문 용어를 반영하여 비즈니스 톤을 유지합니다."
        )


def get_factory() -> TranslationFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return TranslationFactory()
