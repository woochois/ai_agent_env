"""채팅 모델(LLM) 생성 팩토리.

Supervisor가 사용할 Tool calling 지원 채팅 모델을 생성합니다. 비용 추적
콜백(CostTrackingCallback)을 자동으로 부착합니다.
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import get_settings
from app.services.llm import CostTrackingCallback

logger = logging.getLogger(__name__)


def create_chat_model(
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
    **kwargs,
) -> BaseChatModel:
    """Tool calling을 지원하는 채팅 모델을 생성합니다.

    Args:
        model: 모델명 (기본 "gpt-4o-mini").
        temperature: 샘플링 온도.
        **kwargs: ChatOpenAI에 전달할 추가 인자.

    Returns:
        CostTrackingCallback이 부착된 BaseChatModel.
    """
    from langchain_openai import ChatOpenAI

    settings = get_settings()
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY,
        callbacks=[CostTrackingCallback()],
        **kwargs,
    )
