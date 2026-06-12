"""Supervisor Agent (LangGraph) 통합 테스트.

Tool calling을 지원하는 가짜 모델로 ReAct 루프(agent → tools → agent)를 검증합니다.
- 도구 없이 직접 응답
- 도구 호출 → 결과 반영 → 최종 응답
- 세션 ID 처리
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.framework.registry import ToolAgentRegistry
from app.framework.supervisor import SupervisorService
from app.tool_agents.calculator_agent.factory import get_factory as calc_factory


class FakeToolCallingModel(BaseChatModel):
    """순서대로 미리 정의된 AIMessage를 반환하는 가짜 모델 (bind_tools 지원)."""

    responses: list[AIMessage] = []
    index: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake-tool-calling"

    def _next(self) -> AIMessage:
        msg = self.responses[self.index]
        self.index += 1
        return msg

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next())])

    async def _agenerate(
        self, messages, stop=None, run_manager=None, **kwargs
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next())])

    def bind_tools(self, tools: Any, **kwargs: Any) -> "FakeToolCallingModel":
        return self


def _registry_with_calculator() -> ToolAgentRegistry:
    reg = ToolAgentRegistry()
    reg.register(calc_factory())
    return reg


@pytest.mark.asyncio
async def test_supervisor_direct_answer_without_tools():
    """도구 없이 LLM이 직접 답변하는 경우."""
    model = FakeToolCallingModel(responses=[AIMessage(content="직접 답변입니다.")])
    service = SupervisorService.create(model, _registry_with_calculator())

    result = await service.ainvoke(query="안녕")
    assert result["response"] == "직접 답변입니다."
    assert result["session_id"]
    assert result["tool_calls"] == []


@pytest.mark.asyncio
async def test_supervisor_calls_tool_then_answers():
    """LLM이 calculator 도구를 호출하고, 결과를 반영해 최종 답변을 생성한다."""
    tool_call_message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "calculator",
                "args": {"expression": "2 + 3 * 3"},
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )
    final_message = AIMessage(content="계산 결과는 11입니다.")
    model = FakeToolCallingModel(responses=[tool_call_message, final_message])
    service = SupervisorService.create(model, _registry_with_calculator())

    result = await service.ainvoke(
        query="2 + 3 * 3 는?",
        tool_agents={
            "calc": {
                "type": "calculator_agent",
                "name": "calculator",
                "description": "계산기",
            }
        },
    )
    assert result["response"] == "계산 결과는 11입니다."
    assert "calculator" in result["tool_calls"]


@pytest.mark.asyncio
async def test_supervisor_preserves_provided_session_id():
    model = FakeToolCallingModel(responses=[AIMessage(content="ok")])
    service = SupervisorService.create(model, _registry_with_calculator())
    result = await service.ainvoke(query="hi", session_id="my-session")
    assert result["session_id"] == "my-session"


@pytest.mark.asyncio
async def test_supervisor_empty_response_fallback():
    """빈 응답(도구 호출도 없음)은 사용자 안내 메시지로 대체된다."""
    model = FakeToolCallingModel(responses=[AIMessage(content="")])
    service = SupervisorService.create(model, _registry_with_calculator())
    result = await service.ainvoke(query="???")
    assert "이해하지 못했습니다" in result["response"]


def test_build_config_structure():
    model = FakeToolCallingModel(responses=[AIMessage(content="x")])
    service = SupervisorService.create(model, _registry_with_calculator())
    config = service.build_config(
        "sess-1",
        tool_agents={"c": {"type": "calculator_agent", "name": "calculator"}},
        system_prompt="custom",
    )
    conf = config["configurable"]
    assert conf["thread_id"] == "sess-1"
    assert conf["session_id"] == "sess-1"
    assert conf["system_prompt"] == "custom"
    assert "c" in conf["tool_agents"]
