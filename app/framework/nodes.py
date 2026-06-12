"""Supervisor Agent의 LangGraph 노드.

``AgentNode``는 LLM을 호출하여 응답을 생성하거나 Tool 호출을 결정합니다.
설계 참고: klid-aicb의 ``supervisor_agent/nodes.py`` (핵심 로직 간소화).
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import Runnable, RunnableConfig

from app.framework.prompt import PromptGenerator
from app.framework.registry import DynamicToolFactory
from app.framework.state import SupervisorState

logger = logging.getLogger(__name__)


class AgentNode:
    """LLM을 호출하여 응답을 생성하거나 Tool을 선택하는 노드.

    Args:
        model: Tool calling을 지원하는 채팅 모델.
        tool_factory: 활성화된 Tool 생성용 동적 팩토리.
        prompt_generator: 프롬프트 템플릿 생성기.
    """

    def __init__(
        self,
        model: BaseChatModel,
        tool_factory: DynamicToolFactory,
        prompt_generator: PromptGenerator,
    ) -> None:
        self._model = model
        self._tool_factory = tool_factory
        self._prompt_generator = prompt_generator

    async def __call__(
        self, state: SupervisorState, config: RunnableConfig
    ) -> dict[str, Any]:
        """노드 실행: 데이터 캐시 갱신 → LLM 호출 → 상태 갱신."""
        self._upsert_data(state)
        chain = await self._build_chain(config)
        message = await self._invoke(chain, state, config)
        return {"messages": [message], "data": state.get("data", {})}

    async def _build_chain(self, config: RunnableConfig) -> Runnable:
        """config로부터 LLM 체인을 구성합니다 (Tool 바인딩 포함)."""
        tool_agents = config.get("configurable", {}).get("tool_agents", {})
        tools = self._tool_factory.create_tools(tool_agents) if tool_agents else []

        prompt = await self._prompt_generator.create_prompt_template(config, tools)
        if tools:
            return prompt | self._model.bind_tools(tools)
        return prompt | self._model

    async def _invoke(
        self, chain: Runnable, state: SupervisorState, config: RunnableConfig
    ) -> AIMessage:
        """LLM을 호출하고 비정상 응답을 방어적으로 처리합니다."""
        try:
            message: AIMessage = await chain.ainvoke(
                {"messages": state["messages"]}, config=config
            )
        except Exception as exc:  # noqa: BLE001 - LLM 실패 시 graceful 메시지 반환
            logger.error("LLM 호출 중 오류가 발생했습니다: %s", exc, exc_info=True)
            return AIMessage(
                content="죄송합니다. 요청을 처리하는 중 오류가 발생했습니다. "
                "잠시 후 다시 시도해 주세요.",
                additional_kwargs={"error": str(exc), "error_type": type(exc).__name__},
            )

        # Tool 호출도 없고 content도 비어있는 비정상 응답 방어
        if not message.tool_calls and not (message.content or "").strip():
            logger.warning("LLM이 빈 응답을 반환했습니다")
            message.content = (
                "죄송합니다. 질문을 이해하지 못했습니다. 다른 방식으로 질문해 주세요."
            )
        return message

    def _upsert_data(self, state: SupervisorState) -> None:
        """ToolMessage artifact에서 data를 추출하여 상태 캐시에 저장합니다."""
        if "data" not in state or state["data"] is None:
            state["data"] = {}

        for msg in state.get("messages", []):
            if (
                isinstance(msg, ToolMessage)
                and msg.status == "success"
                and isinstance(msg.artifact, dict)
            ):
                artifact = msg.artifact
                data_id = artifact.get("data_id")
                if data_id and data_id not in state["data"]:
                    state["data"][data_id] = {
                        "data": artifact.get("data"),
                        "type": artifact.get("type"),
                    }
