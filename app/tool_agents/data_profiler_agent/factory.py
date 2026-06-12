"""Data Profiler Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.framework.dbutil import DBProvider, default_db_provider
from app.tool_agents.data_profiler_agent.tool import AGENT_TYPE, DataProfilerTool


class DataProfilerFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "Data Profiler"
    category = "Data Quality"
    complexity = "medium"
    summary = "테이블의 행 수, 컬럼별 NULL 비율/고유값 수를 집계합니다."
    tags = ("profiling", "data-quality", "statistics", "de")
    requires = ("postgresql",)

    def __init__(self, db_provider: DBProvider | None = None) -> None:
        self._db_provider = db_provider or default_db_provider

    def create_tool(self, tool_config: dict[str, Any]) -> DataProfilerTool:
        return DataProfilerTool(
            name=tool_config.get("name", "profile_data"),
            description=tool_config.get("description", "테이블 데이터를 프로파일링합니다."),
            db_provider=self._db_provider,
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return "- profile_data: 테이블 데이터의 NULL/고유값 분포를 파악할 때 사용합니다."


def get_factory() -> DataProfilerFactory:
    return DataProfilerFactory()
