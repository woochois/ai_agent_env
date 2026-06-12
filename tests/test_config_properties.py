"""app/config.py 환경 변수 검증 Property 기반 테스트.

Hypothesis를 사용하여 필수 환경 변수 검증 로직의 정확성을 검증합니다.
"""

import contextlib
import os

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.config import Settings

# Feature: docker-ai-agent-dev-env, Property 1: 환경 변수 검증 완전성

REQUIRED_VARS = ["OPENAI_API_KEY", "DATABASE_URL", "ELASTICSEARCH_URL"]

# 유효한 값: 공백이 아닌 출력 가능한 ASCII 문자로만 구성 (strip 후 비어있지 않음 보장)
valid_values = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=50,
)

# 무효한 상태: 환경 변수 누락, 빈 문자열, 공백 문자열
bad_states = st.sampled_from(["missing", "empty", "whitespace"])

# 각 필수 변수의 상태: ("valid", 값) 또는 ("bad", 무효종류)
var_state = st.one_of(
    valid_values.map(lambda v: ("valid", v)),
    bad_states.map(lambda kind: ("bad", kind)),
)

# 세 필수 변수에 대한 상태 조합 생성
config_strategy = st.fixed_dictionaries({var: var_state for var in REQUIRED_VARS})


@contextlib.contextmanager
def patched_env(config):
    """주어진 설정에 따라 환경 변수를 일시적으로 변경하고 종료 시 복원합니다."""
    saved = {var: os.environ.get(var) for var in REQUIRED_VARS}
    try:
        for var, (kind, value) in config.items():
            if kind == "valid":
                os.environ[var] = value
            elif value == "missing":
                os.environ.pop(var, None)
            elif value == "empty":
                os.environ[var] = ""
            else:  # whitespace
                os.environ[var] = "   "
        yield
    finally:
        for var, old in saved.items():
            if old is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = old


@settings(max_examples=200)
@given(config=config_strategy)
def test_env_validation_completeness(config):
    """Property 1: 환경 변수 검증 완전성.

    필수 변수의 임의 부분집합이 누락되거나 빈/공백 문자열인 경우,
    검증은 실패해야 하며 무효한 모든 변수명이 에러 메시지에 포함되어야 한다.

    Validates: Requirements 4.3, 4.6
    """
    bad_vars = [var for var, (kind, _) in config.items() if kind == "bad"]

    # 무효한 변수가 하나 이상 있는 경우만 검증 대상 (Property의 전제)
    if not bad_vars:
        with patched_env(config):
            # 모든 필수 변수가 유효하면 검증 성공해야 함
            settings_obj = Settings(_env_file=None)
            assert settings_obj.OPENAI_API_KEY.strip()
            assert settings_obj.DATABASE_URL.strip()
            assert settings_obj.ELASTICSEARCH_URL.strip()
        return

    with patched_env(config):
        with pytest.raises(Exception) as exc_info:
            Settings(_env_file=None)

    error_msg = str(exc_info.value)
    # 무효/누락된 모든 변수명이 에러 메시지에 정확히 포함되어야 함
    for var in bad_vars:
        assert var in error_msg, (
            f"무효한 변수 '{var}'이(가) 에러 메시지에 누락됨: {error_msg}"
        )
