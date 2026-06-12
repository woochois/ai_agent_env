"""프레임워크 레지스트리 및 동적 팩토리 테스트.

- 자동 발견(auto-discovery): 번들된 예제 에이전트들이 등록되는지
- 수동 등록 및 멱등성
- DynamicToolFactory: 생성, 다중 생성, 알 수 없는 타입 에러
- generate_tool_prompt 조합
"""

from __future__ import annotations

import pytest

from app.framework.base import BaseAgentTool, BaseToolFactory, build_artifact
from app.framework.registry import (
    DynamicToolFactory,
    ToolAgentRegistry,
)


class _DummyTool(BaseAgentTool):
    name: str = "dummy"
    description: str = "더미"

    def _run(self, *args, **kwargs):
        return "", build_artifact("dummy_agent")

    async def _arun(self, *args, **kwargs):
        return "", build_artifact("dummy_agent")


class _DummyFactory(BaseToolFactory):
    agent_type = "dummy_agent"

    def create_tool(self, tool_config):
        return _DummyTool(
            name=tool_config.get("name", "dummy"),
            description=tool_config.get("description", "더미"),
        )

    async def generate_tool_prompt(self, config):
        return "- dummy: 더미 도구"


def test_discover_finds_bundled_agents():
    """번들된 예제 에이전트(echo, calculator, rag_search)가 자동 발견된다."""
    reg = ToolAgentRegistry()
    reg.discover()
    types = reg.available_types()
    assert "echo_agent" in types
    assert "calculator_agent" in types
    assert "rag_search_agent" in types


def test_discover_is_idempotent():
    reg = ToolAgentRegistry()
    first = reg.discover()
    second = reg.discover()
    assert first.keys() == second.keys()


def test_register_requires_agent_type():
    reg = ToolAgentRegistry()

    class _NoType(BaseToolFactory):
        agent_type = ""

        def create_tool(self, tool_config):
            raise NotImplementedError

    with pytest.raises(ValueError):
        reg.register(_NoType())


def test_register_and_get_factory():
    reg = ToolAgentRegistry()
    factory = _DummyFactory()
    reg.register(factory)
    assert reg.get_factory("dummy_agent") is factory
    assert "dummy_agent" in reg.available_types()


def test_dynamic_factory_creates_tool():
    reg = ToolAgentRegistry()
    reg.register(_DummyFactory())
    dtf = DynamicToolFactory(reg)
    tool = dtf.create_tool({"type": "dummy_agent", "name": "d", "description": "x"})
    assert isinstance(tool, _DummyTool)
    assert tool.name == "d"


def test_dynamic_factory_unknown_type_raises():
    reg = ToolAgentRegistry()
    reg.register(_DummyFactory())
    dtf = DynamicToolFactory(reg)
    with pytest.raises(ValueError, match="알 수 없는 Tool Agent 타입"):
        dtf.create_tool({"type": "nonexistent_agent", "name": "n"})


def test_dynamic_factory_missing_type_raises():
    reg = ToolAgentRegistry()
    dtf = DynamicToolFactory(reg)
    with pytest.raises(ValueError, match="'type' 필드가 필요"):
        dtf.create_tool({"name": "n"})


def test_dynamic_factory_creates_multiple_tools():
    reg = ToolAgentRegistry()
    reg.discover()
    dtf = DynamicToolFactory(reg)
    tools = dtf.create_tools(
        {
            "calc": {"type": "calculator_agent", "name": "calculator", "description": "c"},
            "echo": {"type": "echo_agent", "name": "echo", "description": "e"},
        }
    )
    assert len(tools) == 2
    assert {t.name for t in tools} == {"calculator", "echo"}


@pytest.mark.asyncio
async def test_dynamic_factory_generates_combined_prompt():
    reg = ToolAgentRegistry()
    reg.register(_DummyFactory())
    dtf = DynamicToolFactory(reg)
    config = {
        "configurable": {
            "tool_agents": {"d": {"type": "dummy_agent", "name": "dummy"}}
        }
    }
    prompt = await dtf.generate_tool_prompt(config)
    assert "dummy" in prompt
