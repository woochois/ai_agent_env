"""Slow Query Analyzer Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.framework.dbutil import DBProvider, default_db_provider
from app.tool_agents.slow_query_analyzer_agent.tool import (
    AGENT_TYPE,
    SlowQueryAnalyzerTool,
)


class SlowQueryAnalyzerFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "Slow Query Analyzer"
    category = "Performance"
    complexity = "advanced"
    summary = "pg_stat_statements로 평균 실행시간이 높은 쿼리를 분석합니다."
    tags = ("performance", "monitoring", "pg_stat_statements", "dba")
    requires = ("postgresql", "pg_stat_statements")

    def __init__(self, db_provider: DBProvider | None = None) -> None:
        self._db_provider = db_provider or default_db_provider

    def create_tool(self, tool_config: dict[str, Any]) -> SlowQueryAnalyzerTool:
        return SlowQueryAnalyzerTool(
            name=tool_config.get("name", "analyze_slow_queries"),
            description=tool_config.get("description", "느린 쿼리를 분석합니다."),
            db_provider=self._db_provider,
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return "- analyze_slow_queries: 데이터베이스에서 느린 쿼리를 찾아낼 때 사용합니다."


def get_factory() -> SlowQueryAnalyzerFactory:
    return SlowQueryAnalyzerFactory()
