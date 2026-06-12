# Feature: docker-ai-agent-dev-env, Property 4: LLM 비용 계산 정확성
"""LLM 비용 계산 정확성 Property 테스트.

Property 4: LLM 비용 계산 정확성
랜덤 토큰 수(0~100000)와 모델별 단가에 대해 ``calculate_cost`` 가
``round(prompt_tokens × input_price + completion_tokens × output_price, 6)``
으로 정확히 계산되는지 검증한다.

Validates: Requirements 7.5
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.llm import (
    COST_DECIMAL_PLACES,
    DEFAULT_MODEL_PRICE,
    MODEL_PRICING,
    calculate_cost,
    get_model_price,
)


# 단가표에 등록된 알려진 모델명 목록
KNOWN_MODELS = sorted(MODEL_PRICING.keys())

# 토큰 수 범위: 0 ~ 100000 (요구사항)
TOKEN_RANGE = st.integers(min_value=0, max_value=100_000)


def _expected_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """기대 비용을 단가표에서 직접 계산한다 (테스트용 독립 계산)."""
    price = MODEL_PRICING[model]
    raw = (
        prompt_tokens * price["input_price"]
        + completion_tokens * price["output_price"]
    )
    return round(raw, COST_DECIMAL_PLACES)


@settings(max_examples=200)
@given(
    model=st.sampled_from(KNOWN_MODELS),
    prompt_tokens=TOKEN_RANGE,
    completion_tokens=TOKEN_RANGE,
)
def test_calculate_cost_matches_formula(model, prompt_tokens, completion_tokens):
    """Property 4: 알려진 모델에 대해 비용이 공식대로 정확히 계산된다.

    Validates: Requirements 7.5
    """
    expected = _expected_cost(model, prompt_tokens, completion_tokens)
    actual = calculate_cost(model, prompt_tokens, completion_tokens)

    assert actual == expected


@settings(max_examples=200)
@given(
    model=st.sampled_from(KNOWN_MODELS),
    prompt_tokens=TOKEN_RANGE,
    completion_tokens=TOKEN_RANGE,
)
def test_calculate_cost_rounded_to_six_places(model, prompt_tokens, completion_tokens):
    """비용은 항상 소수점 6자리까지 반올림된 값이다.

    Validates: Requirements 7.5
    """
    actual = calculate_cost(model, prompt_tokens, completion_tokens)

    # 반올림된 값과 동일해야 한다 (추가 반올림이 값을 바꾸지 않음).
    assert actual == round(actual, COST_DECIMAL_PLACES)


@settings(max_examples=200)
@given(
    model=st.sampled_from(KNOWN_MODELS),
    prompt_tokens=TOKEN_RANGE,
    completion_tokens=TOKEN_RANGE,
)
def test_calculate_cost_non_negative(model, prompt_tokens, completion_tokens):
    """토큰 수가 0 이상이면 비용은 음수가 될 수 없다.

    Validates: Requirements 7.5
    """
    actual = calculate_cost(model, prompt_tokens, completion_tokens)

    assert actual >= 0.0


@settings(max_examples=200)
@given(
    model=st.sampled_from(KNOWN_MODELS),
    prompt_tokens=TOKEN_RANGE,
    completion_tokens=TOKEN_RANGE,
)
def test_calculate_cost_components_consistent(
    model, prompt_tokens, completion_tokens
):
    """프롬프트/응답 비용 합이 전체 비용과 일치한다 (선형성 확인).

    개별 토큰 종류만 따로 계산한 값을 합산하면, 반올림 오차 범위 내에서
    전체 비용과 동일해야 한다.

    Validates: Requirements 7.5
    """
    price = get_model_price(model)
    prompt_only = prompt_tokens * price["input_price"]
    completion_only = completion_tokens * price["output_price"]
    expected = round(prompt_only + completion_only, COST_DECIMAL_PLACES)

    actual = calculate_cost(model, prompt_tokens, completion_tokens)

    assert math.isclose(actual, expected, abs_tol=0.0)


def test_calculate_cost_zero_tokens_is_zero():
    """토큰이 0이면 비용도 0이다 (구체적 예시)."""
    for model in KNOWN_MODELS:
        assert calculate_cost(model, 0, 0) == 0.0


def test_calculate_cost_known_value_gpt4():
    """gpt-4 단가에 대한 구체적 비용 값 검증."""
    # gpt-4: input 0.03/1K, output 0.06/1K
    # 1000 prompt + 1000 completion = 0.03 + 0.06 = 0.09
    assert calculate_cost("gpt-4", 1000, 1000) == round(0.03 + 0.06, 6)


def test_calculate_cost_negative_tokens_raises():
    """음수 토큰 수는 ValueError 를 발생시킨다."""
    with pytest.raises(ValueError):
        calculate_cost("gpt-4", -1, 0)
    with pytest.raises(ValueError):
        calculate_cost("gpt-4", 0, -1)
