"""Document Agent 팩토리.

Requirements: 4.1, 4.8 (deprecated flags on original factories)
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.document_agent.tool import AGENT_TYPE, DocumentTool


class DocumentFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "Document Expert"
    category = "Documentation"
    complexity = "medium"
    summary = (
        "문서 검토, 보고서 개요, 발표 자료 구성을 통합 제공하는 전문 에이전트입니다."
    )
    tags = ("document", "review", "report", "presentation", "writing")
    requires = ()
    deprecated = False

    def create_tool(self, tool_config: dict[str, Any]) -> DocumentTool:
        return DocumentTool(
            name=tool_config.get("name", "document"),
            description=tool_config.get(
                "description",
                "문서 관련 작업을 통합 제공합니다 "
                "(review, outline_report, assist_presentation).",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- document: 문서 검토(review), 보고서 개요(outline_report), "
            "발표 자료 구성(assist_presentation)을 수행합니다. "
            "sub_command 파라미터로 기능을 선택합니다."
        )


def get_factory() -> DocumentFactory:
    return DocumentFactory()
