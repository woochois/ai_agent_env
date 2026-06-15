"""Document Review Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.document_review_agent.tool import AGENT_TYPE, DocumentReviewTool


class DocumentReviewFactory(BaseToolFactory):
    """DocumentReviewTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE
    display_name = "문서 검토"
    category = "Documentation"
    complexity = "medium"
    summary = "작성한 문서의 문법, 일관성, 논리적 흐름을 검토하고 개선 제안을 제공합니다"
    tags = ("review", "grammar", "quality")
    deprecated = True

    def create_tool(self, tool_config: dict[str, Any]) -> DocumentReviewTool:
        return DocumentReviewTool(
            name=tool_config.get("name", "document_review"),
            description=tool_config.get(
                "description",
                "작성한 문서의 문법, 일관성, 논리적 흐름을 검토하고 개선 제안을 제공합니다. "
                "문서 텍스트와 문서 유형을 입력하면 이슈 목록, 수정 제안, 전체 점수를 반환합니다.",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- document_review: 작성한 문서를 검토할 때 사용합니다. "
            "문서 텍스트와 유형(report/proposal/email/contract/general)을 입력하면 "
            "문법, 일관성, 논리적 흐름을 분석하고 개선 제안을 제공합니다."
        )


def get_factory() -> DocumentReviewFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return DocumentReviewFactory()
