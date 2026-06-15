"""Schema Inspector Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.framework.dbutil import DBProvider, default_db_provider
from app.tool_agents.schema_inspector_agent.tool import AGENT_TYPE, SchemaInspectorTool


class SchemaInspectorFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "Schema Inspector"
    category = "Schema"
    complexity = "medium"
    summary = "테이블의 컬럼/인덱스/제약조건을 조회합니다."
    tags = ("schema", "metadata", "introspection", "dba")
    requires = ("postgresql",)
    deprecated = True

    def __init__(self, db_provider: DBProvider | None = None) -> None:
        self._db_provider = db_provider or default_db_provider

    def create_tool(self, tool_config: dict[str, Any]) -> SchemaInspectorTool:
        return SchemaInspectorTool(
            name=tool_config.get("name", "inspect_schema"),
            description=tool_config.get("description", "테이블 스키마를 조회합니다."),
            db_provider=self._db_provider,
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return "- inspect_schema: 특정 테이블의 구조(컬럼/인덱스/제약)를 확인할 때 사용합니다."


def get_factory() -> SchemaInspectorFactory:
    return SchemaInspectorFactory()
