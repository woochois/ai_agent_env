"""Supervisor Agent 프롬프트 생성기.

시스템 프롬프트와 활성화된 Tool들의 사용법 프롬프트를 동적으로 조합합니다.
설계 참고: klid-aicb의 ``supervisor_agent/prompt.py``.
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from app.framework.registry import DynamicToolFactory

#: 기본 시스템 프롬프트. config의 configurable.system_prompt로 덮어쓸 수 있습니다.
DEFAULT_SYSTEM_PROMPT = """당신은 사용자의 질문을 분석하여 적절한 도구(Tool)를 선택해
정확하고 도움이 되는 답변을 생성하는 AI 어시스턴트입니다.

## 행동 원칙
- 질문에 답하기 위해 필요한 도구가 있으면 적극적으로 호출하세요.
- 도구 실행 결과를 바탕으로 사용자에게 완전한 답변을 생성하세요.
- 질문 언어와 동일한 언어로 답변하세요.
- 도구가 필요 없는 일반적인 질문에는 직접 답변하세요.
- 알 수 없는 내용은 추측하지 말고 솔직하게 모른다고 답하세요."""


class PromptGenerator:
    """Supervisor용 ChatPromptTemplate을 동적으로 생성합니다."""

    def __init__(
        self,
        tool_factory: DynamicToolFactory,
        default_system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self._tool_factory = tool_factory
        self._default_system_prompt = default_system_prompt

    async def create_prompt_template(
        self, config: RunnableConfig, tools: list[BaseTool]
    ) -> ChatPromptTemplate:
        """시스템 프롬프트 + Tool 가이드 + 메시지 히스토리로 템플릿을 구성합니다.

        Args:
            config: 런타임 설정. ``configurable.system_prompt`` 로 시스템 프롬프트 재정의 가능.
            tools: 바인딩된 Tool 목록 (Tool별 가이드 생성에 사용).

        Returns:
            구성된 ChatPromptTemplate.
        """
        configurable = config.get("configurable", {})
        system_prompt = configurable.get(
            "system_prompt", self._default_system_prompt
        )

        if tools:
            tool_prompt = await self._tool_factory.generate_tool_prompt(config)
            if tool_prompt:
                system_prompt = f"{system_prompt}\n\n## 사용 가능한 도구 안내\n{tool_prompt}"

        return ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
