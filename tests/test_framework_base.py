"""프레임워크 기반 클래스 및 유틸리티 테스트.

- build_artifact / build_error_artifact
- auto_error_artifact 데코레이터 (동기/비동기, 예외 변환)
- BaseToolFactory.is_target_tool 기본 동작
"""

from __future__ import annotations

import pytest

from app.framework.base import (
    BaseAgentTool,
    BaseToolFactory,
    auto_error_artifact,
    build_artifact,
    build_error_artifact,
)


def test_build_artifact_includes_type():
    artifact = build_artifact("my_agent", foo="bar", n=1)
    assert artifact == {"type": "my_agent", "foo": "bar", "n": 1}


def test_build_error_artifact_structure():
    artifact = build_error_artifact("my_agent", "사용자 메시지", "상세", extra=[])
    assert artifact["type"] == "my_agent"
    assert artifact["error_message"] == "사용자 메시지"
    assert artifact["error_detail"] == "상세"
    assert artifact["extra"] == []


class _ToolForDecorator(BaseAgentTool):
    name: str = "deco_tool"
    description: str = "데코레이터 테스트용"

    def _run(self, *args, **kwargs):
        return self._sync_logic(kwargs.get("fail", False))

    async def _arun(self, *args, **kwargs):
        return await self._async_logic(kwargs.get("fail", False))

    @auto_error_artifact(agent_type="deco_tool", default_message="실패 메시지")
    def _sync_logic(self, fail: bool):
        if fail:
            raise ValueError("동기 실패")
        return "ok", build_artifact("deco_tool", value=1)

    @auto_error_artifact(agent_type="deco_tool", default_message="실패 메시지", documents=[])
    async def _async_logic(self, fail: bool):
        if fail:
            raise RuntimeError("비동기 실패")
        return "ok", build_artifact("deco_tool", value=2)


def test_auto_error_artifact_sync_success():
    tool = _ToolForDecorator()
    content, artifact = tool._sync_logic(False)
    assert content == "ok"
    assert artifact == {"type": "deco_tool", "value": 1}


def test_auto_error_artifact_sync_catches_exception():
    tool = _ToolForDecorator()
    content, artifact = tool._sync_logic(True)
    assert content == ""
    assert artifact["type"] == "deco_tool"
    assert artifact["error_message"] == "실패 메시지"
    assert "동기 실패" in artifact["error_detail"]


@pytest.mark.asyncio
async def test_auto_error_artifact_async_success():
    tool = _ToolForDecorator()
    content, artifact = await tool._async_logic(False)
    assert content == "ok"
    assert artifact == {"type": "deco_tool", "value": 2}


@pytest.mark.asyncio
async def test_auto_error_artifact_async_catches_exception():
    tool = _ToolForDecorator()
    content, artifact = await tool._async_logic(True)
    assert content == ""
    assert artifact["error_message"] == "실패 메시지"
    assert artifact["documents"] == []
    assert "비동기 실패" in artifact["error_detail"]


def test_auto_error_artifact_rejects_non_basetool():
    @auto_error_artifact(agent_type="x")
    def standalone(self):  # noqa: ANN001
        return "", {}

    with pytest.raises(TypeError):
        standalone("not a tool")


class _MyFactory(BaseToolFactory):
    agent_type = "sample_agent"

    def create_tool(self, tool_config):
        raise NotImplementedError


def test_factory_is_target_tool_matches_agent_type():
    factory = _MyFactory()
    assert factory.is_target_tool("sample_agent") is True
    assert factory.is_target_tool("other_agent") is False


@pytest.mark.asyncio
async def test_factory_default_prompt_is_empty():
    factory = _MyFactory()
    assert await factory.generate_tool_prompt({}) == ""
