"""채팅 모델(LLM) 생성 팩토리.

Supervisor가 사용할 Tool calling 지원 채팅 모델을 생성합니다. 비용 추적
콜백(CostTrackingCallback)을 자동으로 부착합니다.

내부적으로 Model_Router를 사용하여 모델 식별자를 해석하되,
기존 create_chat_model() 함수 시그니처는 유지합니다.

Requirements: 10.6
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

    내부적으로 ModelRouter를 통해 프로바이더를 해석하여 적절한
    ChatModel을 생성합니다. 기존 함수 시그니처는 유지합니다.

    Args:
        model: 모델명 (기본 "gpt-4o-mini"). "provider/model" 형식도 지원.
        temperature: 샘플링 온도.
        **kwargs: ChatModel에 전달할 추가 인자.

    Returns:
        CostTrackingCallback이 부착된 BaseChatModel.
    """
    from app.framework.model_router import get_model_router

    try:
        router = get_model_router()
        provider, model_name = router.resolve(model)
    except (ValueError, Exception):
        # ModelRouter를 사용할 수 없는 경우 기존 방식으로 폴백
        logger.debug("ModelRouter unavailable, falling back to direct ChatOpenAI")
        from langchain_openai import ChatOpenAI

        settings = get_settings()
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=settings.OPENAI_API_KEY,
            callbacks=[CostTrackingCallback()],
            **kwargs,
        )

    # 프로바이더가 OpenAI인 경우 ChatOpenAI를 직접 생성하여 반환
    # (create_chat_model은 동기 함수이므로 ainvoke 대신 모델 인스턴스를 반환)
    from langchain_openai import ChatOpenAI

    from app.framework.model_router import OpenAIProvider

    if isinstance(provider, OpenAIProvider):
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=provider._api_key,
            callbacks=[CostTrackingCallback()],
            **kwargs,
        )

    # Anthropic 프로바이더인 경우
    from app.framework.model_router import AnthropicProvider

    if isinstance(provider, AnthropicProvider):
        try:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=model_name,
                temperature=temperature,
                api_key=provider._api_key,
                callbacks=[CostTrackingCallback()],
                **kwargs,
            )
        except ImportError:
            pass

    # Google 프로바이더인 경우
    from app.framework.model_router import GoogleProvider

    if isinstance(provider, GoogleProvider):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=model_name,
                temperature=temperature,
                google_api_key=provider._api_key,
                callbacks=[CostTrackingCallback()],
                **kwargs,
            )
        except ImportError:
            pass

    # 기타 프로바이더 - 기본 OpenAI 폴백
    logger.warning(
        "Unknown provider type for '%s', falling back to OpenAI", model
    )
    settings = get_settings()
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY,
        callbacks=[CostTrackingCallback()],
        **kwargs,
    )
