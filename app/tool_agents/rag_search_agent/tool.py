"""RAG Search Agent Tool 구현.

Elasticsearch에서 관련 문서를 검색합니다. ES 클라이언트는 provider 콜러블을 통해
주입받으며, ES가 없거나 검색 실패 시 graceful하게 빈 결과를 반환합니다.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact

logger = logging.getLogger(__name__)

AGENT_TYPE = "rag_search_agent"

#: ES 클라이언트를 반환하는 provider 콜러블 타입. None이면 ES 미사용.
ESProvider = Callable[[], Any]


class RagSearchToolInput(BaseModel):
    """RAG Search Tool 입력 스키마."""

    query: str = Field(..., description="문서 검색 질의")


class RagSearchTool(BaseAgentTool):
    """Elasticsearch에서 문서를 검색하는 Tool."""

    es_provider: ESProvider | None = Field(default=None, exclude=True)
    index: str = "documents"
    top_k: int = 5

    name: str = "retrieve_document"
    description: str = (
        "지식베이스(Elasticsearch)에서 질의와 관련된 문서를 검색합니다. "
        "사실 확인이나 문서 기반 답변이 필요할 때 사용하세요."
    )
    args_schema: type[BaseModel] = RagSearchToolInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, query: str, config: RunnableConfig | None = None):
        raise NotImplementedError("RagSearchTool은 비동기(_arun)로만 실행됩니다")

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="문서 검색 중 오류가 발생했습니다",
        documents=[],
    )
    async def _arun(self, query: str, config: RunnableConfig | None = None):
        client = self._resolve_client()
        if client is None:
            logger.warning("Elasticsearch 클라이언트가 없어 검색을 건너뜁니다")
            return "", build_artifact(
                AGENT_TYPE, documents=[], note="elasticsearch_unavailable"
            )

        search_body = {
            "query": {"multi_match": {"query": query, "fields": ["content", "title"]}},
            "size": self.top_k,
            "_source": ["content", "title", "source"],
        }
        response = await client.search(
            index=self.index, body=search_body, ignore_unavailable=True
        )

        documents = self._parse_hits(response)
        return "", build_artifact(AGENT_TYPE, documents=documents)

    def _resolve_client(self) -> Any | None:
        """provider로부터 ES 클라이언트를 해석합니다."""
        if self.es_provider is None:
            return None
        es = self.es_provider()
        # ElasticsearchClient 래퍼이거나 raw client일 수 있음
        return getattr(es, "client", es)

    @staticmethod
    def _parse_hits(response: dict) -> list[dict]:
        """ES 응답에서 문서 목록을 추출합니다."""
        documents: list[dict] = []
        for hit in response.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            documents.append(
                {
                    "document": src.get("content", ""),
                    "reference": src.get("source") or src.get("title", ""),
                    "score": hit.get("_score"),
                }
            )
        return documents

    def format_content(self, message: ToolMessage) -> ToolMessage:
        if not isinstance(message.artifact, dict):
            return message
        documents = message.artifact.get("documents", [])
        if not documents:
            return message.model_copy(
                update={"content": "관련 문서를 찾지 못했습니다."}
            )
        body = "\n\n".join(d.get("document", "") for d in documents)
        instruction = (
            "\n\n[지침] 위 검색 결과를 바탕으로 사용자 질문에 대한 답변을 생성하세요."
        )
        return message.model_copy(update={"content": f"{body}{instruction}"})
