"""Index Advisor Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.framework.dbutil import DBProvider, default_db_provider
from app.tool_agents.index_advisor_agent.tool import AGENT_TYPE, IndexAdvisorTool


class IndexAdvisorFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "Index Advisor"
    category = "Performance"
    complexity = "advanced"
    summary = "쿼리를 분석하여 인덱스 후보와 CREATE INDEX DDL을 추천합니다."
    tags = ("index", "performance", "tuning", "advisor", "dba")
    requires = ("postgresql",)  # EXPLAIN 보강에만 사용, 없어도 휴리스틱 동작

    def __init__(self, db_provider: DBProvider | None = None) -> None:
        self._db_provider = db_provider or default_db_provider

    def create_tool(self, tool_config: dict[str, Any]) -> IndexAdvisorTool:
        return IndexAdvisorTool(
            name=tool_config.get("name", "advise_indexes"),
            description=tool_config.get("description", "인덱스를 추천합니다."),
            db_provider=self._db_provider,
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return "- advise_indexes: 느린 쿼리에 어떤 인덱스를 추가하면 좋을지 추천받을 때 사용합니다."


def get_factory() -> IndexAdvisorFactory:
    return IndexAdvisorFactory()
