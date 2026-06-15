"""Schema Expert Agent 팩토리.

Requirements: 2.1, 2.10
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.framework.dbutil import DBProvider, default_db_provider
from app.tool_agents.schema_expert_agent.tool import AGENT_TYPE, SchemaExpertTool


class SchemaExpertFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "Schema Expert"
    category = "Schema"
    complexity = "advanced"
    summary = (
        "DDL 생성, 스키마 조회, ER 다이어그램, 인덱스 추천을 통합 제공하는 전문 에이전트입니다."
    )
    tags = ("schema", "ddl", "erd", "index", "inspector", "modeling")
    requires = ("postgresql",)
    deprecated = False

    def __init__(self, db_provider: DBProvider | None = None) -> None:
        self._db_provider = db_provider or default_db_provider

    def create_tool(self, tool_config: dict[str, Any]) -> SchemaExpertTool:
        return SchemaExpertTool(
            name=tool_config.get("name", "schema_expert"),
            description=tool_config.get(
                "description",
                "DB 스키마 관련 작업을 통합 제공합니다 "
                "(generate_ddl, inspect_schema, generate_er_diagram, advise_index).",
            ),
            db_provider=self._db_provider,
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- schema_expert: DDL 생성(generate_ddl), 스키마 조회(inspect_schema), "
            "ER 다이어그램(generate_er_diagram), 인덱스 추천(advise_index)을 수행합니다. "
            "sub_command 파라미터로 기능을 선택합니다."
        )


def get_factory() -> SchemaExpertFactory:
    return SchemaExpertFactory()
