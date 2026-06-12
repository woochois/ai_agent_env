"""Data Quality Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.framework.dbutil import DBProvider, default_db_provider
from app.tool_agents.data_quality_agent.tool import AGENT_TYPE, DataQualityTool


class DataQualityFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "Data Quality Checker"
    category = "Data Quality"
    complexity = "advanced"
    summary = "규칙 기반 데이터 품질 검사(not_null/unique/range/accepted_values)를 수행합니다."
    tags = ("data-quality", "validation", "testing", "de", "dw")
    requires = ("postgresql",)

    def __init__(self, db_provider: DBProvider | None = None) -> None:
        self._db_provider = db_provider or default_db_provider

    def create_tool(self, tool_config: dict[str, Any]) -> DataQualityTool:
        return DataQualityTool(
            name=tool_config.get("name", "check_data_quality"),
            description=tool_config.get("description", "데이터 품질을 검사합니다."),
            db_provider=self._db_provider,
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return "- check_data_quality: 테이블 데이터가 규칙(NULL/유일성/범위 등)을 만족하는지 검증할 때 사용합니다."


def get_factory() -> DataQualityFactory:
    return DataQualityFactory()
