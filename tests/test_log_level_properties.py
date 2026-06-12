"""LOG_LEVEL 유효성 검증 폴백 Property 기반 테스트.

# Feature: docker-ai-agent-dev-env, Property 5: LOG_LEVEL 유효성 검증 폴백

Property 5: LOG_LEVEL 유효성 검증 폴백
*For any* 문자열이 {DEBUG, INFO, WARNING, ERROR} 집합에 속하지 않는 경우,
로깅 시스템은 경고 메시지를 출력하고 기본값 INFO 레벨로 동작해야 한다.

LOG_LEVEL 폴백은 두 곳에서 처리됩니다:
1. app.config.Settings.LOG_LEVEL 검증 (model_validator)
2. app.logging_config._get_log_level()

두 구현 모두 동일한 폴백 동작을 보장하는지 검증합니다.

**Validates: Requirements 7.6**
"""

import contextlib
import io
import os
import warnings

from hypothesis import given, settings, strategies as st

from app.config import VALID_LOG_LEVELS, Settings
from app.logging_config import _get_log_level


# --- 입력 전략 ---------------------------------------------------------------

# 임의의 텍스트: 유효/무효가 섞여 있으며, 환경 변수에 안전한 문자만 사용
# (널 바이트는 os.environ 설정 시 ValueError를 발생시키므로 제외)
# (서로게이트 문자 U+D800~U+DFFF는 UTF-8 인코딩이 불가하므로 제외)
_arbitrary_text = st.text(
    alphabet=st.characters(
        blacklist_characters="\x00",
        blacklist_categories=("Cs",),
    ),
    max_size=30,
)

# 임의의 대소문자 조합으로 만든 유효 레벨 (예: "debug", "Info", "WaRnInG")
_valid_levels_any_case = st.sampled_from(sorted(VALID_LOG_LEVELS)).flatmap(
    lambda level: st.sampled_from([level, level.lower(), level.title(), level.swapcase()])
)

# 유효 레벨과 임의 텍스트를 섞은 전략
_mixed_log_levels = st.one_of(_valid_levels_any_case, _arbitrary_text)


def _is_valid(value: str) -> bool:
    """value.upper()가 유효한 로그 레벨 집합에 속하는지 여부."""
    return value.upper() in VALID_LOG_LEVELS


# --- Property 테스트: app.config.Settings -----------------------------------


@settings(max_examples=200)
@given(level=_mixed_log_levels)
def test_settings_log_level_fallback_property(level):
    """Settings.LOG_LEVEL: 무효 값은 경고 후 INFO로, 유효 값은 정규화되어 유지된다."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        settings_obj = Settings(
            _env_file=None,
            OPENAI_API_KEY="sk-test",
            DATABASE_URL="postgresql://u:p@db:5432/db",
            ELASTICSEARCH_URL="http://es:9200",
            LOG_LEVEL=level,
        )

    if _is_valid(level):
        # 유효한 값은 대문자로 정규화되어 그대로 유지
        assert settings_obj.LOG_LEVEL == level.upper()
        assert settings_obj.LOG_LEVEL in VALID_LOG_LEVELS
    else:
        # 무효한 값은 INFO로 폴백되고 경고가 발생해야 함
        assert settings_obj.LOG_LEVEL == "INFO"
        assert len(caught) >= 1
        assert any("LOG_LEVEL" in str(w.message) for w in caught)


# --- Property 테스트: app.logging_config._get_log_level ----------------------


@settings(max_examples=200)
@given(level=_mixed_log_levels)
def test_get_log_level_fallback_property(level):
    """_get_log_level(): 무효 값은 stderr 경고 후 INFO 반환, 유효 값은 그대로 반환."""
    original = os.environ.get("LOG_LEVEL")
    os.environ["LOG_LEVEL"] = level
    stderr_buffer = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr_buffer):
            result = _get_log_level()
    finally:
        if original is None:
            os.environ.pop("LOG_LEVEL", None)
        else:
            os.environ["LOG_LEVEL"] = original

    # 반환값은 항상 유효한 로그 레벨이어야 한다
    assert result in VALID_LOG_LEVELS

    stderr_output = stderr_buffer.getvalue()
    if _is_valid(level):
        assert result == level.upper()
    else:
        # 무효한 값은 INFO로 폴백되고 stderr에 WARNING이 출력되어야 함
        assert result == "INFO"
        assert "WARNING" in stderr_output


# --- 명시적 무효 입력에 대한 폴백 보장 ---------------------------------------


@settings(max_examples=200)
@given(
    level=_arbitrary_text.filter(lambda s: s.upper() not in VALID_LOG_LEVELS)
)
def test_invalid_strings_always_fall_back_to_info(level):
    """{DEBUG, INFO, WARNING, ERROR} 외의 임의 문자열은 항상 INFO로 폴백된다."""
    # config 경로
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        settings_obj = Settings(
            _env_file=None,
            OPENAI_API_KEY="sk-test",
            DATABASE_URL="postgresql://u:p@db:5432/db",
            ELASTICSEARCH_URL="http://es:9200",
            LOG_LEVEL=level,
        )
    assert settings_obj.LOG_LEVEL == "INFO"
    assert len(caught) >= 1

    # logging_config 경로
    original = os.environ.get("LOG_LEVEL")
    os.environ["LOG_LEVEL"] = level
    try:
        result = _get_log_level()
    finally:
        if original is None:
            os.environ.pop("LOG_LEVEL", None)
        else:
            os.environ["LOG_LEVEL"] = original
    assert result == "INFO"
