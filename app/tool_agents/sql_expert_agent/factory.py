"""SQL Expert Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.framework.dbutil import DBProvider, default_db_provider
from app.tool_agents.sql_expert_agent.tool import AGENT_TYPE, SqlExpertTool


class SqlExpertFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "SQL Expert"
    category = "SQL"
    deprecated = False
    complexity = "advanced"
    summary = (
        "SQL 포맷팅, 린트, 실행계획 분석, 느린 쿼리 분석을 통합 제공합니다. "
        "sub_command로 기능을 선택합니다."
    )
    tags = ("sql", "format", "lint", "explain", "performance", "dba")
    requires = ("postgresql",)

    def __init__(self, db_provider: DBProvider | None = None) -> None:
        self._db_provider = db_provider or default_db_provider

    def create_tool(self, tool_config: dict[str, Any]) -> SqlExpertTool:
        return SqlExpertTool(
            name=tool_config.get("name", "sql_expert"),
            description=tool_config.get(
                "description",
                "SQL 포맷팅, 린트, 실행계획 분석, 느린 쿼리 분석을 통합 제공합니다.",
            ),
            db_provider=self._db_provider,
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- sql_expert: SQL 관련 작업을 수행합니다. "
            "sub_command에 format, lint, explain, analyze_slow_query 중 하나를 지정합니다."
        )


def get_factory() -> SqlExpertFactory:
    return SqlExpertFactory()
