"""멀티 모델 라우팅 인프라.

Model_Router는 모델 식별자(예: "anthropic/claude-3-sonnet")를 파싱하여
적절한 LLM_Provider를 선택하고 호출을 위임하는 라우팅 계층입니다.

- ``LLMProvider``: LLM 서비스 프로바이더 추상 인터페이스
- ``ModelRouter``: 모델 식별자 → LLM_Provider 라우팅
- ``OpenAIProvider``: OpenAI ChatOpenAI 기반 프로바이더
- ``AnthropicProvider``: Anthropic ChatAnthropic 기반 프로바이더 (optional)
- ``GoogleProvider``: Google ChatGoogleGenerativeAI 기반 프로바이더 (optional)
- ``get_model_router()``: 싱글톤 ModelRouter 인스턴스 반환

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10, 10.11, 10.12
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConfigurationError(Exception):
    """API 키 등 필수 설정이 누락된 경우 발생하는 예외.

    Requirements: 10.8
    """

    def __init__(self, provider_name: str, variable_name: str) -> None:
        self.provider_name = provider_name
        self.variable_name = variable_name
        super().__init__(
            f"Provider '{provider_name}' requires environment variable "
            f"'{variable_name}' which is not configured"
        )


# ---------------------------------------------------------------------------
# LLMProvider Abstract Base Class
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """LLM 서비스 프로바이더 추상 인터페이스.

    Requirements: 10.1, 10.2
    """

    @abstractmethod
    async def ainvoke(
        self,
        messages: list,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """LLM을 비동기 호출하여 응답 텍스트를 반환합니다.

        Args:
            messages: LangChain 메시지 리스트.
            model: 모델명 (프로바이더 접두사 제외).
            temperature: 샘플링 온도.
            max_tokens: 최대 생성 토큰 수.

        Returns:
            LLM 응답 컨텐츠 텍스트.
        """
        ...


# ---------------------------------------------------------------------------
# ModelRouter
# ---------------------------------------------------------------------------


class ModelRouter:
    """모델 식별자 → LLM_Provider 라우팅.

    Requirements: 10.1, 10.3, 10.4, 10.6, 10.7, 10.10, 10.11, 10.12
    """

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        """프로바이더를 레지스트리에 등록합니다.

        Args:
            name: 프로바이더 이름 (대소문자 무시하여 저장).
            provider: LLMProvider 인스턴스.

        Raises:
            ValueError: 이미 동일 이름이 등록된 경우.

        Requirements: 10.6, 10.12
        """
        key = name.lower()
        if key in self._providers:
            raise ValueError(
                f"Provider '{name}' is already registered. "
                f"Use replace_provider() to replace an existing provider."
            )
        self._providers[key] = provider

    def replace_provider(self, name: str, provider: LLMProvider) -> None:
        """기존 프로바이더를 교체합니다.

        Args:
            name: 프로바이더 이름.
            provider: 새 LLMProvider 인스턴스.

        Requirements: 10.12
        """
        key = name.lower()
        self._providers[key] = provider

    def resolve(self, model_identifier: str) -> tuple[LLMProvider, str]:
        """모델 식별자를 파싱하여 (provider, model_name) 튜플을 반환합니다.

        - "/" 포함 시: 첫 번째 "/"로 분리하여 prefix를 프로바이더명으로 사용
        - "/" 미포함 시: "openai" 프로바이더에 전체 문자열을 모델명으로 사용
        - 프로바이더 이름 조회는 대소문자 무시

        Args:
            model_identifier: 모델 식별자 (예: "anthropic/claude-3-sonnet" 또는 "gpt-4o").

        Returns:
            (LLMProvider 인스턴스, 모델명) 튜플.

        Raises:
            ValueError: 프로바이더가 레지스트리에 없는 경우.

        Requirements: 10.3, 10.4, 10.7, 10.10
        """
        if "/" in model_identifier:
            provider_name, model_name = model_identifier.split("/", 1)
        else:
            provider_name, model_name = "openai", model_identifier

        key = provider_name.lower()
        if key not in self._providers:
            registered = list(self._providers.keys())
            raise ValueError(
                f"Provider '{provider_name}' not found. "
                f"Registered providers: {registered}"
            )

        return self._providers[key], model_name

    async def ainvoke(
        self, model_identifier: str, messages: list, **kwargs: Any
    ) -> str:
        """모델 식별자를 해석하여 적절한 프로바이더로 호출을 위임합니다.

        프로바이더 내부 예외는 RuntimeError로 래핑합니다.

        Args:
            model_identifier: 모델 식별자.
            messages: LangChain 메시지 리스트.
            **kwargs: temperature, max_tokens 등 추가 파라미터.

        Returns:
            LLM 응답 텍스트.

        Raises:
            RuntimeError: 프로바이더 호출 중 예외 발생 시.

        Requirements: 10.11
        """
        provider, model_name = self.resolve(model_identifier)
        provider_key = self._get_provider_key(provider)

        try:
            return await provider.ainvoke(
                messages=messages,
                model=model_name,
                **kwargs,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Provider '{provider_key}' failed for model '{model_name}': "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    def _get_provider_key(self, provider: LLMProvider) -> str:
        """프로바이더 인스턴스의 등록된 이름을 역검색합니다."""
        for key, p in self._providers.items():
            if p is provider:
                return key
        return "unknown"


# ---------------------------------------------------------------------------
# Provider Implementations
# ---------------------------------------------------------------------------


class OpenAIProvider(LLMProvider):
    """OpenAI ChatOpenAI 기반 프로바이더.

    Requirements: 10.5, 10.9
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def ainvoke(
        self,
        messages: list,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        from langchain_openai import ChatOpenAI

        from app.services.llm import CostTrackingCallback

        llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=self._api_key,
            callbacks=[CostTrackingCallback()],
        )
        response = await llm.ainvoke(messages)
        return str(response.content)


class AnthropicProvider(LLMProvider):
    """Anthropic ChatAnthropic 기반 프로바이더 (optional import).

    Requirements: 10.1
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def ainvoke(
        self,
        messages: list,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError(
                "langchain_anthropic is not installed. "
                "Install it with: pip install langchain-anthropic"
            ) from exc

        from app.services.llm import CostTrackingCallback

        llm = ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=self._api_key,
            callbacks=[CostTrackingCallback()],
        )
        response = await llm.ainvoke(messages)
        return str(response.content)


class GoogleProvider(LLMProvider):
    """Google ChatGoogleGenerativeAI 기반 프로바이더 (optional import).

    Requirements: 10.1
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def ainvoke(
        self,
        messages: list,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError(
                "langchain_google_genai is not installed. "
                "Install it with: pip install langchain-google-genai"
            ) from exc

        from app.services.llm import CostTrackingCallback

        llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            max_output_tokens=max_tokens,
            google_api_key=self._api_key,
            callbacks=[CostTrackingCallback()],
        )
        response = await llm.ainvoke(messages)
        return str(response.content)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_model_router_instance: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    """싱글톤 ModelRouter 인스턴스를 반환합니다.

    환경 변수를 기반으로 사용 가능한 프로바이더를 자동 등록합니다.

    - OPENAI_API_KEY → OpenAIProvider 등록
    - ANTHROPIC_API_KEY → AnthropicProvider 등록
    - GOOGLE_API_KEY → GoogleProvider 등록

    Requirements: 10.6, 10.9
    """
    global _model_router_instance
    if _model_router_instance is not None:
        return _model_router_instance

    router = ModelRouter()

    # OpenAI (기본 프로바이더)
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        router.register_provider("openai", OpenAIProvider(api_key=openai_key))
        logger.info("Registered OpenAI provider")
    else:
        logger.warning("OPENAI_API_KEY not set; OpenAI provider not available")

    # Anthropic (optional)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        router.register_provider("anthropic", AnthropicProvider(api_key=anthropic_key))
        logger.info("Registered Anthropic provider")

    # Google (optional)
    google_key = os.environ.get("GOOGLE_API_KEY", "")
    if google_key:
        router.register_provider("google", GoogleProvider(api_key=google_key))
        logger.info("Registered Google provider")

    _model_router_instance = router
    return _model_router_instance


def reset_model_router() -> None:
    """싱글톤 인스턴스를 초기화합니다 (테스트 전용)."""
    global _model_router_instance
    _model_router_instance = None
