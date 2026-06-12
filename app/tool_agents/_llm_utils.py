"""비즈니스 Tool Agent 공통 LLM 유틸리티.

모든 비즈니스 에이전트가 공유하는 LLM 호출 및 응답 파싱 헬퍼를 제공합니다.
"""

from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.framework.model import create_chat_model


def parse_json_response(response_text: str) -> dict | None:
    """LLM 응답 텍스트에서 JSON 객체를 추출하여 파싱합니다.

    추출 전략:
        1. ```json ... ``` 또는 ``` ... ``` 코드 블록 내부의 JSON을 파싱
        2. 코드 블록이 없거나 파싱 실패 시 전체 응답을 JSON으로 파싱
        3. 모두 실패하면 None 반환

    Args:
        response_text: LLM이 반환한 원시 텍스트.

    Returns:
        파싱된 dict 또는 None.
    """
    # 1. 코드 블록에서 JSON 추출
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response_text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 2. 전체를 JSON으로 파싱
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        return None


async def call_llm(
    system_prompt: str,
    user_input: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.3,
) -> str:
    """LLM을 비동기로 호출하여 응답 텍스트를 반환합니다.

    create_chat_model()로 모델 인스턴스를 생성하고, 시스템/유저 메시지를
    구성한 뒤 ainvoke()를 호출합니다.

    Args:
        system_prompt: 시스템 프롬프트 (에이전트 역할 정의).
        user_input: 사용자 입력 텍스트.
        model: 사용할 모델명 (기본 "gpt-4o-mini").
        temperature: 샘플링 온도 (기본 0.3).

    Returns:
        LLM 응답의 content 문자열.
    """
    model_instance = create_chat_model(model=model, temperature=temperature)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input),
    ]
    response = await model_instance.ainvoke(messages)
    return response.content
