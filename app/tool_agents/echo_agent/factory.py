"""Echo Agent 팩토리.

레지스트리 규약: ``get_factory() -> BaseToolFactory`` 를 노출합니다.
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.echo_agent.tool import AGENT_TYPE, EchoTool


class EchoAgentFactory(BaseToolFactory):
    """EchoTool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE

    def create_tool(self, tool_config: dict[str, Any]) -> EchoTool:
        return EchoTool(
            name=tool_config.get("name", "echo"),
            description=tool_config.get(
                "description", "입력한 텍스트를 그대로 되돌려줍니다."
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        return "- echo: 사용자가 입력한 텍스트를 그대로 확인하고 싶을 때 사용합니다."


def get_factory() -> EchoAgentFactory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return EchoAgentFactory()
