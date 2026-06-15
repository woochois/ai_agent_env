"""SQL Lint Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.sql_lint_agent.tool import AGENT_TYPE, SqlLintTool


class SqlLintFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "SQL Linter"
    category = "SQL"
    deprecated = True
    complexity = "simple"
    summary = "SQL 안티패턴(SELECT *, WHERE 없는 DELETE, 선행 와일드카드 등)을 검출합니다."
    tags = ("sql", "lint", "best-practice", "review")
    requires = ()

    def create_tool(self, tool_config: dict[str, Any]) -> SqlLintTool:
        return SqlLintTool(
            name=tool_config.get("name", "lint_sql"),
            description=tool_config.get("description", "SQL 안티패턴을 검출합니다."),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return "- lint_sql: SQL의 품질/위험 패턴을 점검해 달라고 할 때 사용합니다."


def get_factory() -> SqlLintFactory:
    return SqlLintFactory()
