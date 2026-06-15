"""Model_Router Property 기반 테스트.

Hypothesis를 사용하여 ModelRouter의 라우팅 결정론성과
프로바이더 레지스트리 관리의 정확성을 검증합니다.

**Property 10: Model_Router 라우팅 결정론성**
**Property 11: Model_Router 프로바이더 레지스트리 관리**
**Validates: Requirements 10.3, 10.4, 10.6, 10.7, 10.8, 10.10, 10.11, 10.12**
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.framework.model_router import (
    ConfigurationError,
    LLMProvider,
    ModelRouter,
    OpenAIProvider,
    reset_model_router,
)

# Feature: agent-consolidation-advanced, Property 10: Model_Router 라우팅 결정론성
# Feature: agent-consolidation-advanced, Property 11: Model_Router 프로바이더 레지스트리 관리


# ---------------------------------------------------------------------------
# Helper: A mock LLMProvider for testing
# ---------------------------------------------------------------------------


class MockProvider(LLMProvider):
    """테스트용 Mock LLM Provider."""

    def __init__(self, name: str = "mock"):
        self.name = name
        self.last_call_args: dict | None = None

    async def ainvoke(
        self,
        messages: list,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        self.last_call_args = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        return f"response from {self.name}/{model}"


class FailingProvider(LLMProvider):
    """항상 예외를 발생시키는 테스트용 Provider."""

    def __init__(self, error: Exception):
        self._error = error

    async def ainvoke(
        self,
        messages: list,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        raise self._error


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# 프로바이더 이름: ASCII 영문 소문자와 숫자로 구성된 1~20자 문자열
_provider_chars = "abcdefghijklmnopqrstuvwxyz0123456789"
provider_name_st = st.text(
    alphabet=st.sampled_from(_provider_chars),
    min_size=1,
    max_size=20,
)

# 모델 이름: ASCII 영숫자, 하이픈, 점, 언더스코어로 구성
_model_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._"
model_name_st = st.text(
    alphabet=st.sampled_from(_model_chars),
    min_size=1,
    max_size=50,
)

# "/" 포함 모델 식별자 (provider/model)
prefixed_model_id_st = st.builds(
    lambda p, m: f"{p}/{m}",
    provider_name_st,
    model_name_st,
)

# "/" 미포함 모델 식별자 (model만)
bare_model_id_st = model_name_st.filter(lambda s: "/" not in s)


# ---------------------------------------------------------------------------
# Property 10: Model_Router 라우팅 결정론성
# ---------------------------------------------------------------------------


class TestModelRouterRoutingDeterminism:
    """Property 10: 모델 식별자 라우팅이 결정론적임을 검증합니다.

    **Validates: Requirements 10.3, 10.4, 10.10**
    """

    @settings(max_examples=20)
    @given(provider_name=provider_name_st, model_name=model_name_st)
    def test_prefix_split_on_first_slash(self, provider_name: str, model_name: str):
        """'/' 포함 시 첫 번째 '/'에서 분리하여 provider/model로 해석한다.

        **Validates: Requirements 10.3**
        """
        assume(len(provider_name) > 0 and len(model_name) > 0)

        router = ModelRouter()
        provider = MockProvider(provider_name)
        router.register_provider(provider_name, provider)

        model_identifier = f"{provider_name}/{model_name}"
        resolved_provider, resolved_model = router.resolve(model_identifier)

        assert resolved_provider is provider
        assert resolved_model == model_name

    @settings(max_examples=20)
    @given(model_name=bare_model_id_st)
    def test_no_slash_defaults_to_openai(self, model_name: str):
        """'/' 미포함 시 'openai' 프로바이더에 전체 문자열을 모델명으로 사용한다.

        **Validates: Requirements 10.4**
        """
        assume(len(model_name) > 0)

        router = ModelRouter()
        openai_provider = MockProvider("openai")
        router.register_provider("openai", openai_provider)

        resolved_provider, resolved_model = router.resolve(model_name)

        assert resolved_provider is openai_provider
        assert resolved_model == model_name

    @settings(max_examples=20)
    @given(
        provider_name=provider_name_st,
        model_name=model_name_st,
        case_variant=st.sampled_from(["lower", "upper", "title", "mixed"]),
    )
    def test_case_insensitive_provider_lookup(
        self, provider_name: str, model_name: str, case_variant: str
    ):
        """프로바이더 이름 조회는 대소문자를 무시한다.

        **Validates: Requirements 10.10**
        """
        assume(len(provider_name) > 0 and len(model_name) > 0)

        router = ModelRouter()
        provider = MockProvider(provider_name)
        router.register_provider(provider_name, provider)

        # 다양한 대소문자 변형으로 접근
        if case_variant == "lower":
            lookup_name = provider_name.lower()
        elif case_variant == "upper":
            lookup_name = provider_name.upper()
        elif case_variant == "title":
            lookup_name = provider_name.title()
        else:  # mixed
            lookup_name = "".join(
                c.upper() if i % 2 else c.lower()
                for i, c in enumerate(provider_name)
            )

        model_identifier = f"{lookup_name}/{model_name}"
        resolved_provider, resolved_model = router.resolve(model_identifier)

        assert resolved_provider is provider
        assert resolved_model == model_name

    @settings(max_examples=10)
    @given(
        provider_name=provider_name_st,
        model_name=model_name_st,
    )
    def test_repeated_calls_return_same_result(
        self, provider_name: str, model_name: str
    ):
        """동일 식별자로 반복 호출 시 동일한 결과를 반환한다.

        **Validates: Requirements 10.3**
        """
        assume(len(provider_name) > 0 and len(model_name) > 0)

        router = ModelRouter()
        provider = MockProvider(provider_name)
        router.register_provider(provider_name, provider)

        model_identifier = f"{provider_name}/{model_name}"
        result1 = router.resolve(model_identifier)
        result2 = router.resolve(model_identifier)

        assert result1[0] is result2[0]
        assert result1[1] == result2[1]

    @settings(max_examples=10)
    @given(model_name=model_name_st)
    def test_model_name_with_slashes_preserves_after_first(self, model_name: str):
        """모델명에 추가 '/'가 있어도 첫 번째에서만 분리한다.

        **Validates: Requirements 10.3**
        """
        assume(len(model_name) > 0)

        router = ModelRouter()
        provider = MockProvider("test")
        router.register_provider("test", provider)

        # "test/model/variant/v2" → provider="test", model="model/variant/v2"
        complex_model = f"submodel/{model_name}"
        model_identifier = f"test/{complex_model}"

        resolved_provider, resolved_model = router.resolve(model_identifier)
        assert resolved_provider is provider
        assert resolved_model == complex_model


# ---------------------------------------------------------------------------
# Property 11: Model_Router 프로바이더 레지스트리 관리
# ---------------------------------------------------------------------------


class TestModelRouterProviderRegistryManagement:
    """Property 11: 프로바이더 레지스트리 관리가 올바르게 동작함을 검증합니다.

    **Validates: Requirements 10.6, 10.7, 10.8, 10.11, 10.12**
    """

    @settings(max_examples=20)
    @given(provider_name=provider_name_st, model_name=model_name_st)
    def test_registered_provider_is_routable(
        self, provider_name: str, model_name: str
    ):
        """register_provider 후 해당 프로바이더로 라우팅 가능해야 한다.

        **Validates: Requirements 10.6**
        """
        assume(len(provider_name) > 0 and len(model_name) > 0)

        router = ModelRouter()
        provider = MockProvider(provider_name)
        router.register_provider(provider_name, provider)

        resolved_provider, resolved_model = router.resolve(
            f"{provider_name}/{model_name}"
        )
        assert resolved_provider is provider
        assert resolved_model == model_name

    @settings(max_examples=10)
    @given(provider_name=provider_name_st)
    def test_duplicate_registration_raises_valueerror(self, provider_name: str):
        """이미 등록된 프로바이더 이름으로 재등록 시 ValueError를 발생한다.

        **Validates: Requirements 10.12**
        """
        assume(len(provider_name) > 0)

        router = ModelRouter()
        provider1 = MockProvider("first")
        provider2 = MockProvider("second")

        router.register_provider(provider_name, provider1)

        with pytest.raises(ValueError) as exc_info:
            router.register_provider(provider_name, provider2)

        assert provider_name in str(exc_info.value)
        assert "already registered" in str(exc_info.value).lower()

    @settings(max_examples=10)
    @given(
        requested_name=provider_name_st,
        registered_names=st.lists(provider_name_st, min_size=1, max_size=5, unique=True),
    )
    def test_missing_provider_raises_valueerror_with_details(
        self, requested_name: str, registered_names: list[str]
    ):
        """미등록 프로바이더 요청 시 요청된 이름과 등록 목록을 포함한 ValueError.

        **Validates: Requirements 10.7**
        """
        assume(len(requested_name) > 0)
        # requested_name이 registered_names에 없음을 보장
        assume(requested_name.lower() not in {n.lower() for n in registered_names})

        router = ModelRouter()
        for name in registered_names:
            router.register_provider(name, MockProvider(name))

        with pytest.raises(ValueError) as exc_info:
            router.resolve(f"{requested_name}/some-model")

        error_msg = str(exc_info.value)
        assert requested_name in error_msg
        # 등록된 프로바이더 목록이 메시지에 포함되어야 함
        for name in registered_names:
            assert name.lower() in error_msg.lower()

    @settings(max_examples=10)
    @given(provider_name=provider_name_st, model_name=model_name_st)
    def test_provider_exception_wrapped_in_runtimeerror(
        self, provider_name: str, model_name: str
    ):
        """프로바이더 ainvoke 예외가 RuntimeError로 래핑되어야 한다.

        RuntimeError 메시지에는 프로바이더명, 모델명, 원본 에러가 포함된다.

        **Validates: Requirements 10.11**
        """
        assume(len(provider_name) > 0 and len(model_name) > 0)

        original_error = ValueError("rate limit exceeded")
        router = ModelRouter()
        router.register_provider(provider_name, FailingProvider(original_error))

        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(
                router.ainvoke(f"{provider_name}/{model_name}", [])
            )

        error_msg = str(exc_info.value)
        assert provider_name.lower() in error_msg.lower()
        assert model_name in error_msg
        assert "rate limit exceeded" in error_msg

    def test_configuration_error_contains_provider_and_variable(self):
        """ConfigurationError에 프로바이더명과 환경변수명이 포함되어야 한다.

        **Validates: Requirements 10.8**
        """
        error = ConfigurationError(
            provider_name="anthropic",
            variable_name="ANTHROPIC_API_KEY",
        )
        assert "anthropic" in str(error).lower()
        assert "ANTHROPIC_API_KEY" in str(error)

    @settings(max_examples=10)
    @given(provider_name=provider_name_st)
    def test_replace_provider_overwrites_existing(self, provider_name: str):
        """replace_provider는 기존 프로바이더를 교체한다.

        **Validates: Requirements 10.12**
        """
        assume(len(provider_name) > 0)

        router = ModelRouter()
        provider1 = MockProvider("first")
        provider2 = MockProvider("second")

        router.register_provider(provider_name, provider1)
        router.replace_provider(provider_name, provider2)

        resolved, _ = router.resolve(f"{provider_name}/model")
        assert resolved is provider2


# ---------------------------------------------------------------------------
# Example-Based Unit Tests
# ---------------------------------------------------------------------------


class TestModelRouterExamples:
    """ModelRouter의 주요 시나리오에 대한 예제 기반 단위 테스트."""

    def test_openai_default_routing(self):
        """'gpt-4o-mini' → openai 프로바이더로 라우팅."""
        router = ModelRouter()
        provider = MockProvider("openai")
        router.register_provider("openai", provider)

        resolved_provider, model_name = router.resolve("gpt-4o-mini")
        assert resolved_provider is provider
        assert model_name == "gpt-4o-mini"

    def test_anthropic_prefix_routing(self):
        """'anthropic/claude-3-sonnet' → anthropic 프로바이더로 라우팅."""
        router = ModelRouter()
        provider = MockProvider("anthropic")
        router.register_provider("anthropic", provider)

        resolved_provider, model_name = router.resolve("anthropic/claude-3-sonnet")
        assert resolved_provider is provider
        assert model_name == "claude-3-sonnet"

    def test_google_prefix_routing(self):
        """'google/gemini-pro' → google 프로바이더로 라우팅."""
        router = ModelRouter()
        provider = MockProvider("google")
        router.register_provider("google", provider)

        resolved_provider, model_name = router.resolve("google/gemini-pro")
        assert resolved_provider is provider
        assert model_name == "gemini-pro"

    def test_case_insensitive_examples(self):
        """대소문자 변형이 모두 동일한 프로바이더로 해석됨."""
        router = ModelRouter()
        provider = MockProvider("openai")
        router.register_provider("openai", provider)

        for variant in ["OpenAI/gpt-4", "OPENAI/gpt-4", "openai/gpt-4"]:
            resolved_provider, model_name = router.resolve(variant)
            assert resolved_provider is provider
            assert model_name == "gpt-4"

    def test_empty_registry_raises_valueerror(self):
        """빈 레지스트리에서 resolve 시 ValueError."""
        router = ModelRouter()

        with pytest.raises(ValueError) as exc_info:
            router.resolve("gpt-4o")

        assert "openai" in str(exc_info.value).lower()

    def test_ainvoke_success(self):
        """ainvoke 성공 시 프로바이더의 응답을 반환한다."""
        router = ModelRouter()
        provider = MockProvider("openai")
        router.register_provider("openai", provider)

        result = asyncio.run(
            router.ainvoke("gpt-4o-mini", [{"role": "user", "content": "hello"}])
        )
        assert "openai" in result
        assert "gpt-4o-mini" in result

    def test_ainvoke_with_prefix(self):
        """ainvoke에서 prefix 포함 식별자가 올바르게 해석된다."""
        router = ModelRouter()
        provider = MockProvider("anthropic")
        router.register_provider("anthropic", provider)

        result = asyncio.run(
            router.ainvoke("anthropic/claude-3-sonnet", [])
        )
        assert "anthropic" in result
        assert "claude-3-sonnet" in result

    def test_register_provider_makes_routing_work(self):
        """register_provider 후 즉시 라우팅 가능."""
        router = ModelRouter()
        provider = MockProvider("custom")
        router.register_provider("custom", provider)

        resolved, model = router.resolve("custom/my-model")
        assert resolved is provider
        assert model == "my-model"
