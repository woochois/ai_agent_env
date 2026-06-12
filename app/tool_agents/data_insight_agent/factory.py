"""Data Insight Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.data_insight_agent.tool import AGENT_TYPE, DataInsightTool


class DataInsightFactory(BaseToolFactory):
    """DataInsightTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE
    display_name = "데이터 인사이트"
    category = "Analytics"
    complexity = "medium"
    summary = "데이터를 분석하여 패턴, 이상치, 트렌드를 식별하고 인사이트를 도출합니다"
    tags = ("data", "analysis", "insight")

    def create_tool(self, tool_config: dict[str, Any]) -> DataInsightTool:
        return DataInsightTool(
            name=tool_config.get("name", "data_insight"),
            description=tool_config.get(
                "description",
                "데이터를 분석하여 패턴, 이상치, 트렌드를 식별하고 인사이트를 도출합니다. "
                "CSV나 테이블 형식 데이터와 분석 관점을 입력하면 구조화된 분석 결과를 반환합니다.",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- data_insight: 데이터를 분석할 때 사용합니다. "
            "CSV나 테이블 데이터와 관점(sales/cost/hr/customer/general)을 입력하면 "
            "패턴, 이상치, 트렌드를 분석하고 인사이트를 도출합니다."
        )


def get_factory() -> DataInsightFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return DataInsightFactory()
