"""RAG Search Agent 팩토리.

ES 클라이언트는 provider 콜러블로 주입합니다. 기본 provider는 ``app.main.get_es``를
지연 호출하여 전역 ElasticsearchClient를 반환하며, 테스트 시에는 커스텀 provider를
주입할 수 있습니다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.rag_search_agent.tool import AGENT_TYPE, ESProvider, RagSearchTool


def _default_es_provider() -> Any | None:
    """전역 ElasticsearchClient를 지연 조회하는 기본 provider."""
    try:
        from app.main import get_es

        return get_es()
    except Exception:  # noqa: BLE001 - 앱 컨텍스트 밖에서는 None
        return None


class RagSearchAgentFactory(BaseToolFactory):
    """RagSearchTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE

    def __init__(self, es_provider: ESProvider | None = None) -> None:
        self._es_provider: Callable[[], Any] = es_provider or _default_es_provider

    def create_tool(self, tool_config: dict[str, Any]) -> RagSearchTool:
        return RagSearchTool(
            name=tool_config.get("name", "retrieve_document"),
            description=tool_config.get(
                "description",
                "지식베이스에서 질의와 관련된 문서를 검색합니다.",
            ),
            index=tool_config.get("index", "documents"),
            top_k=tool_config.get("top_k", 5),
            es_provider=self._es_provider,
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- retrieve_document: 문서 기반 사실 확인이나 지식베이스 검색이 "
            "필요할 때 사용합니다."
        )


def get_factory() -> RagSearchAgentFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return RagSearchAgentFactory()
