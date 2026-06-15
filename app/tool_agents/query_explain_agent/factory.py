"""Query Explain Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.framework.dbutil import DBProvider, default_db_provider
from app.tool_agents.query_explain_agent.tool import AGENT_TYPE, QueryExplainTool


class QueryExplainFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "Query Explain"
    category = "Performance"
    deprecated = True
    complexity = "medium"
    summary = "쿼리 실행계획(EXPLAIN)을 분석하여 비용/스캔 방식/경고를 제공합니다."
    tags = ("explain", "performance", "query-plan", "tuning")
    requires = ("postgresql",)

    def __init__(self, db_provider: DBProvider | None = None) -> None:
        self._db_provider = db_provider or default_db_provider

    def create_tool(self, tool_config: dict[str, Any]) -> QueryExplainTool:
        return QueryExplainTool(
            name=tool_config.get("name", "explain_query"),
            description=tool_config.get("description", "쿼리 실행계획을 분석합니다."),
            db_provider=self._db_provider,
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return "- explain_query: 쿼리의 실행계획/성능 특성을 분석할 때 사용합니다."


def get_factory() -> QueryExplainFactory:
    return QueryExplainFactory()
