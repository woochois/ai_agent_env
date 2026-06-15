"""DDL Generator Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.ddl_generator_agent.tool import AGENT_TYPE, DDLGeneratorTool


class DDLGeneratorFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "DDL Generator"
    category = "Schema"
    complexity = "medium"
    summary = "컬럼 명세로부터 CREATE TABLE / 인덱스 DDL을 생성합니다."
    tags = ("ddl", "schema", "create-table", "modeling")
    requires = ()
    deprecated = True

    def create_tool(self, tool_config: dict[str, Any]) -> DDLGeneratorTool:
        return DDLGeneratorTool(
            name=tool_config.get("name", "generate_ddl"),
            description=tool_config.get("description", "CREATE TABLE DDL을 생성합니다."),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return "- generate_ddl: 테이블 설계 명세로부터 CREATE TABLE DDL을 만들 때 사용합니다."


def get_factory() -> DDLGeneratorFactory:
    return DDLGeneratorFactory()
