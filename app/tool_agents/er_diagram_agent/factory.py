"""ER Diagram Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.framework.dbutil import DBProvider, default_db_provider
from app.tool_agents.er_diagram_agent.tool import AGENT_TYPE, ERDiagramTool


class ERDiagramFactory(BaseToolFactory):
    agent_type = AGENT_TYPE
    display_name = "ER Diagram Generator"
    category = "Schema"
    complexity = "medium"
    summary = "스키마의 테이블/FK 관계로부터 Mermaid ER 다이어그램을 생성합니다."
    tags = ("erd", "schema", "mermaid", "modeling", "dm")
    requires = ("postgresql",)

    def __init__(self, db_provider: DBProvider | None = None) -> None:
        self._db_provider = db_provider or default_db_provider

    def create_tool(self, tool_config: dict[str, Any]) -> ERDiagramTool:
        return ERDiagramTool(
            name=tool_config.get("name", "generate_erd"),
            description=tool_config.get("description", "Mermaid ER 다이어그램을 생성합니다."),
            db_provider=self._db_provider,
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return "- generate_erd: 스키마 구조를 ER 다이어그램으로 시각화할 때 사용합니다."


def get_factory() -> ERDiagramFactory:
    return ERDiagramFactory()
