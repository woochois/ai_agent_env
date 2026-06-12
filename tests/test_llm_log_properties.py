# Feature: docker-ai-agent-dev-env, Property 3: LLM 로그 항목 완전성
"""LLM 로그 항목 완전성 Property 테스트.

**Property 3: LLM 로그 항목 완전성**

*For any* LLM API 호출(모델명, 프롬프트, 응답, 토큰 수와 무관하게), 생성된 로그
항목은 유효한 JSON이며 반드시 timestamp, level, model, prompt_tokens,
completion_tokens, total_tokens, duration_ms, estimated_cost_usd 필드를 모두
포함해야 한다.

이 테스트는 ``build_cost_log_record`` 가 만든 비용/사용량 필드를 실제 로거 +
``JsonFormatter`` 파이프라인으로 흘려보낸 뒤, 출력된 로그가 유효한 JSON이며
필수 필드를 모두 포함하는지 검증합니다.

**Validates: Requirements 7.1, 7.5**
"""

import json
import logging
from io import StringIO

from hypothesis import given, settings
from hypothesis import strategies as st

from app.logging_config import _create_json_formatter
from app.services.llm import MODEL_PRICING, build_cost_log_record


# 로그 항목에 반드시 포함되어야 하는 필수 필드 (Requirement 7.1, 7.5)
REQUIRED_FIELDS = {
    "timestamp",
    "level",
    "model",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "duration_ms",
    "estimated_cost_usd",
}


def _emit_log_and_parse(record: dict) -> dict:
    """비용 로그 레코드를 실제 로거 + JsonFormatter 로 출력하고 파싱합니다.

    ``logging_config._create_json_formatter`` 가 asctime→timestamp,
    levelname→level 로 필드명을 변경하므로, 출력 JSON에는 timestamp/level
    필드가 포함됩니다. ``record`` 의 필드는 ``extra`` 로 주입되어 JSON에
    그대로 직렬화됩니다.

    Args:
        record: ``build_cost_log_record`` 가 생성한 로그 extra 딕셔너리.

    Returns:
        dict: 파싱된 JSON 로그 항목.
    """
    buffer = StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(_create_json_formatter())

    logger = logging.getLogger("test.llm_log_properties")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info("LLM call completed", extra=record)
    handler.flush()

    output = buffer.getvalue().strip()
    return json.loads(output)


# 알려진 모델명 + 임의 문자열 + None 을 혼합하여 생성
_model_strategy = st.one_of(
    st.sampled_from(sorted(MODEL_PRICING.keys())),
    st.text(min_size=0, max_size=40),
    st.none(),
)

_token_strategy = st.integers(min_value=0, max_value=100_000)
_duration_strategy = st.floats(
    min_value=0.0,
    max_value=600_000.0,
    allow_nan=False,
    allow_infinity=False,
)
_total_tokens_strategy = st.one_of(st.none(), st.integers(min_value=0, max_value=200_000))


@settings(max_examples=200)
@given(
    model=_model_strategy,
    prompt_tokens=_token_strategy,
    completion_tokens=_token_strategy,
    duration_ms=_duration_strategy,
    total_tokens=_total_tokens_strategy,
)
def test_llm_log_record_is_valid_json_with_all_required_fields(
    model,
    prompt_tokens,
    completion_tokens,
    duration_ms,
    total_tokens,
):
    """랜덤 모델명/토큰/응답시간으로 생성된 로그가 유효한 JSON이며 필수 필드를 모두 포함한다."""
    record = build_cost_log_record(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        duration_ms=duration_ms,
        total_tokens=total_tokens,
    )

    # 실제 로거 + JsonFormatter 를 통과시켜 출력 (유효한 JSON 이어야 파싱 성공)
    parsed = _emit_log_and_parse(record)

    # 모든 필수 필드가 포함되어야 한다
    missing = REQUIRED_FIELDS - parsed.keys()
    assert not missing, f"로그 항목에 필수 필드가 누락됨: {missing} (parsed={parsed})"

    # 각 필드의 타입/값 정합성 확인
    assert isinstance(parsed["timestamp"], str) and parsed["timestamp"]
    assert parsed["level"] == "INFO"
    assert isinstance(parsed["model"], str) and parsed["model"]
    assert parsed["prompt_tokens"] == prompt_tokens
    assert parsed["completion_tokens"] == completion_tokens
    assert isinstance(parsed["total_tokens"], int)
    assert isinstance(parsed["duration_ms"], (int, float))
    assert isinstance(parsed["estimated_cost_usd"], (int, float))
