"""call_llm 유틸리티 Property 기반 테스트.

Hypothesis를 사용하여 call_llm의 파라미터 검증 및 동작 정확성을 검증합니다.

**Property 9: call_llm 파라미터 검증**
**Validates: Requirements 6.1, 6.6, 6.8, 6.9, 6.10**
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.tool_agents._llm_utils import call_llm, _DEFAULT_MODEL

# Feature: agent-consolidation-advanced, Property 9: call_llm 파라미터 검증


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# 유효한 비공백 문자열 (system_prompt, user_input 용)
non_empty_text_st = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())

# 공백만 있는 문자열
whitespace_only_st = st.sampled_from(["", " ", "  ", "\t", "\n", "  \t\n  "])

# 유효한 temperature (0.0 ~ 2.0)
valid_temperature_st = st.floats(min_value=0.0, max_value=2.0, allow_nan=False, allow_infinity=False)

# 범위 밖 temperature
invalid_temperature_low_st = st.floats(max_value=-0.01, allow_nan=False, allow_infinity=False).filter(lambda x: x < 0.0)
invalid_temperature_high_st = st.floats(min_value=2.01, max_value=100.0, allow_nan=False, allow_infinity=False)

# 유효한 max_tokens (1 ~ 128000)
valid_max_tokens_st = st.integers(min_value=1, max_value=128000)

# 범위 밖 max_tokens
invalid_max_tokens_low_st = st.integers(max_value=0)
invalid_max_tokens_high_st = st.integers(min_value=128001, max_value=1000000)

# 모델 이름 전략
valid_model_st = st.sampled_from([
    "gpt-4o-mini", "gpt-4o", "gpt-4-turbo",
    "anthropic/claude-3-sonnet", "google/gemini-pro",
])


# ---------------------------------------------------------------------------
# Property 9: call_llm 파라미터 검증 - 빈 입력 검증
# ---------------------------------------------------------------------------


class TestCallLlmInputValidation:
    """call_llm의 입력 검증이 올바르게 동작함을 검증합니다.

    **Validates: Requirements 6.8**
    """

    @settings(max_examples=100)
    @given(
        empty_prompt=whitespace_only_st,
        user_input=non_empty_text_st,
    )
    def test_empty_system_prompt_raises_valueerror(
        self, empty_prompt: str, user_input: str
    ):
        """system_prompt가 빈 문자열 또는 공백만일 경우 ValueError를 발생시킨다.

        **Validates: Requirements 6.8**
        """
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(call_llm(system_prompt=empty_prompt, user_input=user_input))
        assert "system_prompt" in str(exc_info.value)

    @settings(max_examples=100)
    @given(
        system_prompt=non_empty_text_st,
        empty_input=whitespace_only_st,
    )
    def test_empty_user_input_raises_valueerror(
        self, system_prompt: str, empty_input: str
    ):
        """user_input이 빈 문자열 또는 공백만일 경우 ValueError를 발생시킨다.

        **Validates: Requirements 6.8**
        """
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(call_llm(system_prompt=system_prompt, user_input=empty_input))
        assert "user_input" in str(exc_info.value)

    def test_none_system_prompt_raises_valueerror(self):
        """system_prompt가 None일 경우 ValueError를 발생시킨다.

        **Validates: Requirements 6.8**
        """
        with pytest.raises(ValueError):
            asyncio.run(call_llm(system_prompt=None, user_input="hello"))

    def test_none_user_input_raises_valueerror(self):
        """user_input이 None일 경우 ValueError를 발생시킨다.

        **Validates: Requirements 6.8**
        """
        with pytest.raises(ValueError):
            asyncio.run(call_llm(system_prompt="You are helpful.", user_input=None))


# ---------------------------------------------------------------------------
# Property 9: call_llm 파라미터 검증 - temperature 범위
# ---------------------------------------------------------------------------


class TestCallLlmTemperatureValidation:
    """call_llm의 temperature 범위 검증을 테스트합니다.

    **Validates: Requirements 6.9**
    """

    @settings(max_examples=100)
    @given(temp=invalid_temperature_low_st)
    def test_temperature_below_zero_raises_valueerror(self, temp: float):
        """temperature가 0.0 미만일 경우 ValueError를 발생시킨다.

        **Validates: Requirements 6.9**
        """
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(
                call_llm(
                    system_prompt="test",
                    user_input="test",
                    temperature=temp,
                )
            )
        assert "temperature" in str(exc_info.value)
        assert "0.0" in str(exc_info.value)
        assert "2.0" in str(exc_info.value)

    @settings(max_examples=100)
    @given(temp=invalid_temperature_high_st)
    def test_temperature_above_two_raises_valueerror(self, temp: float):
        """temperature가 2.0 초과일 경우 ValueError를 발생시킨다.

        **Validates: Requirements 6.9**
        """
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(
                call_llm(
                    system_prompt="test",
                    user_input="test",
                    temperature=temp,
                )
            )
        assert "temperature" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Property 9: call_llm 파라미터 검증 - max_tokens 범위
# ---------------------------------------------------------------------------


class TestCallLlmMaxTokensValidation:
    """call_llm의 max_tokens 범위 검증을 테스트합니다.

    **Validates: Requirements 6.10**
    """

    @settings(max_examples=100)
    @given(tokens=invalid_max_tokens_low_st)
    def test_max_tokens_below_one_raises_valueerror(self, tokens: int):
        """max_tokens가 1 미만일 경우 ValueError를 발생시킨다.

        **Validates: Requirements 6.10**
        """
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(
                call_llm(
                    system_prompt="test",
                    user_input="test",
                    max_tokens=tokens,
                )
            )
        assert "max_tokens" in str(exc_info.value)
        assert "1" in str(exc_info.value)
        assert "128000" in str(exc_info.value)

    @settings(max_examples=100)
    @given(tokens=invalid_max_tokens_high_st)
    def test_max_tokens_above_limit_raises_valueerror(self, tokens: int):
        """max_tokens가 128000 초과일 경우 ValueError를 발생시킨다.

        **Validates: Requirements 6.10**
        """
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(
                call_llm(
                    system_prompt="test",
                    user_input="test",
                    max_tokens=tokens,
                )
            )
        assert "max_tokens" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Property 9: call_llm 파라미터 검증 - 유효 입력 시 동작
# ---------------------------------------------------------------------------


class TestCallLlmValidInputs:
    """유효한 입력이 주어졌을 때 call_llm이 올바르게 동작하는지 검증합니다.

    **Validates: Requirements 6.1, 6.6**
    """

    @settings(max_examples=100, deadline=None)
    @given(
        system_prompt=non_empty_text_st,
        user_input=non_empty_text_st,
        temperature=valid_temperature_st,
        max_tokens=valid_max_tokens_st,
    )
    def test_valid_inputs_return_string_or_raise_runtime_error(
        self,
        system_prompt: str,
        user_input: str,
        temperature: float,
        max_tokens: int,
    ):
        """유효한 입력일 경우 비빈 문자열을 반환하거나 RuntimeError를 발생시킨다.

        **Validates: Requirements 6.1, 6.6**
        """
        mock_router = AsyncMock()
        mock_router.ainvoke = AsyncMock(return_value="LLM response")

        with patch("app.framework.model_router.get_model_router", return_value=mock_router):
            result = asyncio.run(
                call_llm(
                    system_prompt=system_prompt,
                    user_input=user_input,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            )
            assert isinstance(result, str)
            assert len(result) > 0

    @settings(max_examples=50)
    @given(
        system_prompt=non_empty_text_st,
        user_input=non_empty_text_st,
    )
    def test_provider_exception_propagates_as_runtime_error(
        self, system_prompt: str, user_input: str
    ):
        """프로바이더 예외 발생 시 RuntimeError가 전파된다.

        **Validates: Requirements 6.6**
        """
        mock_router = AsyncMock()
        mock_router.ainvoke = AsyncMock(
            side_effect=RuntimeError("Provider 'openai' failed for model 'gpt-4o-mini': AuthError: invalid key")
        )

        with patch("app.framework.model_router.get_model_router", return_value=mock_router):
            with pytest.raises(RuntimeError) as exc_info:
                asyncio.run(
                    call_llm(
                        system_prompt=system_prompt,
                        user_input=user_input,
                    )
                )
            assert "openai" in str(exc_info.value).lower() or "gpt-4o-mini" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Property 9: call_llm 파라미터 검증 - 기본 모델 처리
# ---------------------------------------------------------------------------


class TestCallLlmDefaultModel:
    """model 파라미터가 None 또는 빈 문자열일 때 기본값을 사용하는지 검증합니다.

    **Validates: Requirements 6.5 (via Requirements 6.1)**
    """

    @settings(max_examples=50)
    @given(
        empty_model=st.sampled_from([None, "", " ", "  "]),
        system_prompt=non_empty_text_st,
        user_input=non_empty_text_st,
    )
    def test_empty_model_uses_default(
        self, empty_model: str | None, system_prompt: str, user_input: str
    ):
        """model이 None/빈 문자열/공백이면 'gpt-4o-mini'를 사용한다.

        **Validates: Requirements 6.5**
        """
        mock_router = AsyncMock()
        mock_router.ainvoke = AsyncMock(return_value="response")

        with patch("app.framework.model_router.get_model_router", return_value=mock_router):
            asyncio.run(
                call_llm(
                    system_prompt=system_prompt,
                    user_input=user_input,
                    model=empty_model,
                )
            )
            # ainvoke의 첫 번째 인자가 "gpt-4o-mini"여야 한다
            call_args = mock_router.ainvoke.call_args
            assert call_args[0][0] == _DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Example-Based Unit Tests
# ---------------------------------------------------------------------------


class TestCallLlmExamples:
    """call_llm의 주요 시나리오에 대한 예제 기반 단위 테스트."""

    def test_successful_invocation_returns_response(self):
        """정상 호출 시 LLM 응답 텍스트를 반환한다.

        **Validates: Requirements 6.1**
        """
        mock_router = AsyncMock()
        mock_router.ainvoke = AsyncMock(return_value="Hello, I am an AI assistant.")

        with patch("app.framework.model_router.get_model_router", return_value=mock_router):
            result = asyncio.run(
                call_llm(
                    system_prompt="You are helpful.",
                    user_input="What is Python?",
                )
            )
            assert result == "Hello, I am an AI assistant."
            # 올바른 메시지가 전달되었는지 확인
            call_args = mock_router.ainvoke.call_args
            assert call_args[0][0] == "gpt-4o-mini"
            messages = call_args[0][1]
            assert len(messages) == 2
            assert messages[0].content == "You are helpful."
            assert messages[1].content == "What is Python?"

    def test_custom_model_is_used(self):
        """커스텀 모델 식별자가 올바르게 전달된다."""
        mock_router = AsyncMock()
        mock_router.ainvoke = AsyncMock(return_value="response")

        with patch("app.framework.model_router.get_model_router", return_value=mock_router):
            asyncio.run(
                call_llm(
                    system_prompt="system",
                    user_input="user",
                    model="anthropic/claude-3-sonnet",
                )
            )
            call_args = mock_router.ainvoke.call_args
            assert call_args[0][0] == "anthropic/claude-3-sonnet"

    def test_temperature_and_max_tokens_passed(self):
        """temperature, max_tokens 파라미터가 router에 올바르게 전달된다."""
        mock_router = AsyncMock()
        mock_router.ainvoke = AsyncMock(return_value="response")

        with patch("app.framework.model_router.get_model_router", return_value=mock_router):
            asyncio.run(
                call_llm(
                    system_prompt="system",
                    user_input="user",
                    temperature=1.5,
                    max_tokens=2048,
                )
            )
            call_kwargs = mock_router.ainvoke.call_args[1]
            assert call_kwargs["temperature"] == 1.5
            assert call_kwargs["max_tokens"] == 2048

    def test_is_async_function(self):
        """call_llm은 async function이다.

        **Validates: Requirements 6.7**
        """
        import inspect
        assert inspect.iscoroutinefunction(call_llm)

    def test_boundary_temperature_zero(self):
        """temperature=0.0 (최솟값) 통과."""
        mock_router = AsyncMock()
        mock_router.ainvoke = AsyncMock(return_value="ok")

        with patch("app.framework.model_router.get_model_router", return_value=mock_router):
            result = asyncio.run(
                call_llm(system_prompt="s", user_input="u", temperature=0.0)
            )
            assert result == "ok"

    def test_boundary_temperature_two(self):
        """temperature=2.0 (최댓값) 통과."""
        mock_router = AsyncMock()
        mock_router.ainvoke = AsyncMock(return_value="ok")

        with patch("app.framework.model_router.get_model_router", return_value=mock_router):
            result = asyncio.run(
                call_llm(system_prompt="s", user_input="u", temperature=2.0)
            )
            assert result == "ok"

    def test_boundary_max_tokens_one(self):
        """max_tokens=1 (최솟값) 통과."""
        mock_router = AsyncMock()
        mock_router.ainvoke = AsyncMock(return_value="ok")

        with patch("app.framework.model_router.get_model_router", return_value=mock_router):
            result = asyncio.run(
                call_llm(system_prompt="s", user_input="u", max_tokens=1)
            )
            assert result == "ok"

    def test_boundary_max_tokens_128000(self):
        """max_tokens=128000 (최댓값) 통과."""
        mock_router = AsyncMock()
        mock_router.ainvoke = AsyncMock(return_value="ok")

        with patch("app.framework.model_router.get_model_router", return_value=mock_router):
            result = asyncio.run(
                call_llm(system_prompt="s", user_input="u", max_tokens=128000)
            )
            assert result == "ok"

    def test_error_propagation_includes_model_name(self):
        """프로바이더 에러 시 RuntimeError에 모델명이 포함된다.

        **Validates: Requirements 6.6**
        """
        mock_router = AsyncMock()
        mock_router.ainvoke = AsyncMock(
            side_effect=RuntimeError(
                "Provider 'openai' failed for model 'gpt-4o-mini': "
                "AuthenticationError: Invalid API key"
            )
        )

        with patch("app.framework.model_router.get_model_router", return_value=mock_router):
            with pytest.raises(RuntimeError) as exc_info:
                asyncio.run(
                    call_llm(system_prompt="s", user_input="u")
                )
            assert "gpt-4o-mini" in str(exc_info.value)
            assert "openai" in str(exc_info.value).lower()
