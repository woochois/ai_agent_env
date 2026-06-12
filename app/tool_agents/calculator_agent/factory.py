"""Calculator Agent 팩토리."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.calculator_agent.tool import AGENT_TYPE, CalculatorTool


class CalculatorAgentFactory(BaseToolFactory):
    """CalculatorTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE

    def create_tool(self, tool_config: dict[str, Any]) -> CalculatorTool:
        return CalculatorTool(
            name=tool_config.get("name", "calculator"),
            description=tool_config.get(
                "description",
                "산술식을 계산합니다. 사칙연산, 거듭제곱, 괄호를 지원합니다.",
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return (
            "- calculator: 숫자 계산이 필요할 때 사용합니다. "
            "사칙연산, 거듭제곱, 괄호를 포함한 산술식을 정확히 계산합니다."
        )


def get_factory() -> CalculatorAgentFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return CalculatorAgentFactory()
