"""SQL Formatter Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.sql_formatter_agent.tool import AGENT_TYPE, SqlFormatterTool


class SqlFormatterFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "SQL Formatter"
    category = "SQL"
    deprecated = True
    complexity = "simple"
    summary = "SQL 쿼리를 읽기 좋게 정렬/포맷합니다 (키워드 대문자화, 절 줄바꿈)."
    tags = ("sql", "format", "lint", "style")
    requires = ()

    def create_tool(self, tool_config: dict[str, Any]) -> SqlFormatterTool:
        return SqlFormatterTool(
            name=tool_config.get("name", "format_sql"),
            description=tool_config.get("description", "SQL 쿼리를 읽기 좋게 포맷합니다."),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return "- format_sql: 사용자가 SQL을 보기 좋게 정렬/포맷해 달라고 할 때 사용합니다."


def get_factory() -> SqlFormatterFactory:
    return SqlFormatterFactory()
