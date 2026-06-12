"""Supervisor Agent: LangGraph 기반 멀티 Tool Agent 오케스트레이터.

ReAct 루프(agent ⟷ tools)로 여러 Tool Agent를 오케스트레이션합니다.
``build_supervisor_graph``로 그래프를 만들고, ``SupervisorService``로 간편하게
대화를 실행합니다.

설계 참고: klid-aicb의 ``supervisor_agent/graph.py`` (체크포인터 부분 간소화).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.framework.nodes import AgentNode
from app.framework.prompt import DEFAULT_SYSTEM_PROMPT, PromptGenerator
from app.framework.registry import DynamicToolFactory, ToolAgentRegistry
from app.framework.state import SupervisorState

logger = logging.getLogger(__name__)


def build_supervisor_graph(
    model: BaseChatModel,
    registry: ToolAgentRegistry,
    checkpointer: Any | None = None,
) -> CompiledStateGraph:
    """Supervisor LangGraph를 빌드하여 컴파일합니다.

    그래프 구조::

        START → agent → (tools_condition)
                 ↑           ↓
                 └── tools ──┘

    Args:
        model: Tool calling을 지원하는 채팅 모델.
        registry: Tool Agent 레지스트리 (자동 발견된 팩토리 포함).
        checkpointer: 상태 영속화용 체크포인터. None이면 InMemorySaver 사용.

    Returns:
        컴파일된 LangGraph (CompiledStateGraph).
    """
    tool_factory = DynamicToolFactory(registry)
    prompt_generator = PromptGenerator(tool_factory)
    agent_node = AgentNode(model, tool_factory, prompt_generator)

    async def dynamic_tool_node(state: SupervisorState, config) -> dict:
        """런타임 config로부터 Tool을 동적 생성하여 실행하는 노드."""
        tool_agents = config.get("configurable", {}).get("tool_agents", {})
        tools = tool_factory.create_tools(tool_agents) if tool_agents else []
        node = ToolNode(tools)
        return await node.ainvoke(state, config)

    graph = (
        StateGraph(SupervisorState)
        .add_node("agent", agent_node)
        .add_node("tools", dynamic_tool_node)
        .set_entry_point("agent")
        .add_conditional_edges("agent", tools_condition)
        .add_edge("tools", "agent")
    )

    return graph.compile(checkpointer=checkpointer or InMemorySaver())


class SupervisorService:
    """Supervisor Agent 실행을 캡슐화한 고수준 서비스.

    FastAPI 라우터 등에서 간단히 ``ainvoke``/``astream``을 호출하여 사용합니다.

    Args:
        graph: 컴파일된 Supervisor 그래프.
        tool_factory: 응답 후처리(format_content)용 동적 팩토리.
    """

    def __init__(
        self, graph: CompiledStateGraph, tool_factory: DynamicToolFactory
    ) -> None:
        self._graph = graph
        self._tool_factory = tool_factory

    @classmethod
    def create(
        cls,
        model: BaseChatModel,
        registry: ToolAgentRegistry,
        checkpointer: Any | None = None,
    ) -> "SupervisorService":
        """모델과 레지스트리로부터 서비스를 생성하는 팩토리 메서드."""
        graph = build_supervisor_graph(model, registry, checkpointer)
        return cls(graph, DynamicToolFactory(registry))

    def build_config(
        self,
        session_id: str,
        tool_agents: dict[str, dict[str, Any]] | None = None,
        system_prompt: str | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """그래프 실행용 RunnableConfig를 구성합니다.

        Args:
            session_id: 대화 세션 식별자 (체크포인터 thread_id).
            tool_agents: 활성화할 Tool Agent 설정 ``{key: {"type","name","description",...}}``.
            system_prompt: 시스템 프롬프트 재정의 (None이면 기본값).
            **extra: configurable에 추가할 기타 설정.

        Returns:
            ``{"configurable": {...}}`` 형태의 RunnableConfig.
        """
        configurable: dict[str, Any] = {
            "thread_id": session_id,
            "session_id": session_id,
            "tool_agents": tool_agents or {},
            **extra,
        }
        if system_prompt is not None:
            configurable["system_prompt"] = system_prompt
        return {"configurable": configurable}

    async def ainvoke(
        self,
        query: str,
        session_id: str | None = None,
        tool_agents: dict[str, dict[str, Any]] | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """단일 질의를 실행하고 최종 응답을 반환합니다.

        Args:
            query: 사용자 질문.
            session_id: 대화 세션 식별자. None이면 새로 생성.
            tool_agents: 활성화할 Tool Agent 설정.
            system_prompt: 시스템 프롬프트 재정의.

        Returns:
            ``{"response", "session_id", "sources", "tool_calls"}`` 딕셔너리.
        """
        session_id = session_id or str(uuid.uuid4())
        config = self.build_config(session_id, tool_agents, system_prompt)

        result = await self._graph.ainvoke(
            {"query": query, "messages": [HumanMessage(content=query)], "data": {}},
            config=config,
        )

        messages = result.get("messages", [])
        response_text = self._extract_final_text(messages)
        sources = self._extract_sources(messages)

        return {
            "response": response_text,
            "session_id": session_id,
            "sources": sources,
            "tool_calls": self._extract_tool_calls(messages),
        }

    @staticmethod
    def _extract_final_text(messages: list) -> str:
        """마지막 AIMessage의 텍스트 응답을 추출합니다."""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and (msg.content or "").strip():
                return msg.content if isinstance(msg.content, str) else str(msg.content)
        return ""

    @staticmethod
    def _extract_sources(messages: list) -> list[str]:
        """ToolMessage artifact에서 출처(sources/documents)를 수집합니다."""
        sources: list[str] = []
        for msg in messages:
            if isinstance(msg, ToolMessage) and isinstance(msg.artifact, dict):
                for doc in msg.artifact.get("documents", []):
                    ref = doc.get("reference") if isinstance(doc, dict) else None
                    if ref:
                        sources.append(ref)
                sources.extend(msg.artifact.get("sources", []))
        return sources

    @staticmethod
    def _extract_tool_calls(messages: list) -> list[str]:
        """실행된 Tool 이름 목록을 수집합니다."""
        names: list[str] = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                names.append(msg.name)
        return names
