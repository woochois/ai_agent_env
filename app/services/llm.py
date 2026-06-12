"""LLM 호출 비용 추적 콜백 모듈.

LangChain ``BaseCallbackHandler`` 를 상속한 ``CostTrackingCallback`` 을 제공하여
모든 LLM API 호출의 토큰 사용량, 소요 시간, 비용 추정값을 JSON 구조화 로그로
기록합니다.

비용 계산 로직은 property 테스트(3.3, 3.4)가 직접 호출할 수 있도록
독립적인 순수 함수(``calculate_cost``, ``build_cost_log_record``)로 분리합니다.

Requirements: 7.1, 7.5
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 모델별 단가표 (per-token, USD 기준)
# ---------------------------------------------------------------------------
#
# 비용 계산식: (prompt_tokens × input_price + completion_tokens × output_price)
#
# input_price / output_price 는 "토큰 1개당" USD 단가입니다.
# 일반적으로 공개되는 1K 토큰당 단가를 1000으로 나눈 값입니다.
# 예) gpt-4: 입력 $0.03 / 1K → 토큰당 0.00003, 출력 $0.06 / 1K → 토큰당 0.00006
#
# 단가는 토큰당 가격을 명시적으로 표현하기 위해 1K 단가를 1000으로 나눠 정의합니다.
ModelPrice = Dict[str, float]

MODEL_PRICING: Dict[str, ModelPrice] = {
    # OpenAI GPT-4 계열
    "gpt-4": {"input_price": 0.03 / 1000, "output_price": 0.06 / 1000},
    "gpt-4-32k": {"input_price": 0.06 / 1000, "output_price": 0.12 / 1000},
    "gpt-4-turbo": {"input_price": 0.01 / 1000, "output_price": 0.03 / 1000},
    "gpt-4o": {"input_price": 0.005 / 1000, "output_price": 0.015 / 1000},
    "gpt-4o-mini": {"input_price": 0.00015 / 1000, "output_price": 0.0006 / 1000},
    # OpenAI GPT-3.5 계열
    "gpt-3.5-turbo": {"input_price": 0.0005 / 1000, "output_price": 0.0015 / 1000},
    "gpt-3.5-turbo-16k": {"input_price": 0.003 / 1000, "output_price": 0.004 / 1000},
}

# 단가표에 없는 모델에 적용할 기본 단가 (0으로 두어 비용 0 처리)
DEFAULT_MODEL_PRICE: ModelPrice = {"input_price": 0.0, "output_price": 0.0}

# 비용 반올림 소수점 자리수 (Requirement 7.5)
COST_DECIMAL_PLACES = 6


def get_model_price(model: Optional[str]) -> ModelPrice:
    """모델명에 해당하는 단가 정보를 반환합니다.

    정확히 일치하는 모델명이 없으면 prefix(접두사) 매칭을 시도하고,
    그래도 없으면 기본 단가(0)를 반환합니다.

    Args:
        model: 모델명 (예: "gpt-4", "gpt-3.5-turbo").

    Returns:
        ModelPrice: {"input_price": float, "output_price": float}
    """
    if not model:
        return dict(DEFAULT_MODEL_PRICE)

    # 정확히 일치
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]

    # prefix 매칭 (예: "gpt-4-0613" → "gpt-4")
    # 더 긴 키가 우선하도록 길이 내림차순으로 검사
    for key in sorted(MODEL_PRICING, key=len, reverse=True):
        if model.startswith(key):
            return MODEL_PRICING[key]

    return dict(DEFAULT_MODEL_PRICE)


def calculate_cost(
    model: Optional[str],
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """LLM 호출 비용을 추정합니다.

    비용 = (prompt_tokens × input_price + completion_tokens × output_price)
    결과는 소수점 6자리까지 반올림합니다. (Requirement 7.5)

    Args:
        model: 모델명. 단가표에 없으면 기본 단가(0)가 적용됩니다.
        prompt_tokens: 프롬프트(입력) 토큰 수 (>= 0).
        completion_tokens: 응답(출력) 토큰 수 (>= 0).

    Returns:
        float: 추정 비용(USD), 소수점 6자리까지 반올림된 값.

    Raises:
        ValueError: 토큰 수가 음수인 경우.
    """
    if prompt_tokens < 0 or completion_tokens < 0:
        raise ValueError(
            "토큰 수는 0 이상이어야 합니다: "
            f"prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}"
        )

    price = get_model_price(model)
    cost = (
        prompt_tokens * price["input_price"]
        + completion_tokens * price["output_price"]
    )
    return round(cost, COST_DECIMAL_PLACES)


def build_cost_log_record(
    model: Optional[str],
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: float,
    total_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """LLM 호출 로그에 포함될 비용/사용량 필드를 구성합니다.

    로그 항목에는 model, prompt_tokens, completion_tokens, total_tokens,
    duration_ms, estimated_cost_usd 필드가 포함됩니다. (Requirement 7.1, 7.5)

    timestamp 와 level 필드는 로깅 프레임워크(JsonFormatter)가
    자동으로 추가합니다.

    Args:
        model: 모델명.
        prompt_tokens: 프롬프트(입력) 토큰 수.
        completion_tokens: 응답(출력) 토큰 수.
        duration_ms: LLM 호출 소요 시간 (밀리초).
        total_tokens: 총 토큰 수. None 이면 prompt + completion 으로 계산.

    Returns:
        Dict[str, Any]: 로그 extra 필드로 사용할 딕셔너리.
    """
    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens

    return {
        "model": model or "unknown",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "duration_ms": round(float(duration_ms), 3),
        "estimated_cost_usd": calculate_cost(model, prompt_tokens, completion_tokens),
    }


def _extract_token_usage(response: LLMResult) -> Dict[str, int]:
    """LLMResult 에서 토큰 사용량을 추출합니다.

    LangChain 버전/제공자에 따라 토큰 사용량 위치가 다를 수 있어
    여러 위치를 순차적으로 확인합니다.

    Args:
        response: LLM 호출 결과.

    Returns:
        Dict[str, int]: prompt_tokens, completion_tokens, total_tokens.
    """
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    # 1) llm_output["token_usage"] (OpenAI 등에서 일반적)
    llm_output = getattr(response, "llm_output", None) or {}
    token_usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
    if token_usage:
        prompt_tokens = int(token_usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(token_usage.get("completion_tokens", 0) or 0)
        total_tokens = int(token_usage.get("total_tokens", 0) or 0)

    # 2) generation 메시지의 usage_metadata (신규 표준)
    if prompt_tokens == 0 and completion_tokens == 0:
        try:
            for gen_list in response.generations:
                for gen in gen_list:
                    message = getattr(gen, "message", None)
                    usage = getattr(message, "usage_metadata", None)
                    if usage:
                        prompt_tokens += int(usage.get("input_tokens", 0) or 0)
                        completion_tokens += int(usage.get("output_tokens", 0) or 0)
                        total_tokens += int(usage.get("total_tokens", 0) or 0)
        except (AttributeError, TypeError):
            pass

    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def _extract_model_name(
    response: LLMResult,
    serialized: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Optional[str]:
    """LLMResult / serialized 정보에서 모델명을 추출합니다."""
    llm_output = getattr(response, "llm_output", None) or {}
    model = llm_output.get("model_name") or llm_output.get("model")
    if model:
        return model

    invocation_params = kwargs.get("invocation_params") or {}
    model = invocation_params.get("model_name") or invocation_params.get("model")
    if model:
        return model

    if serialized:
        kwargs_dict = serialized.get("kwargs") or {}
        model = kwargs_dict.get("model_name") or kwargs_dict.get("model")
        if model:
            return model

    return None


class CostTrackingCallback(BaseCallbackHandler):
    """LLM 호출 비용을 추적하여 JSON 구조화 로그로 기록하는 콜백 핸들러.

    ``on_llm_start`` 에서 시작 시각을 기록하고, ``on_llm_end`` 에서
    토큰 사용량, 소요 시간, 추정 비용을 계산하여 로그에 남깁니다.

    동일 핸들러 인스턴스가 여러 LLM 실행에 재사용될 수 있으므로
    실행별 시작 시각은 run_id 를 키로 하는 딕셔너리에 저장합니다.

    Requirements: 7.1, 7.5
    """

    def __init__(self, logger_instance: Optional[logging.Logger] = None) -> None:
        """콜백 핸들러를 초기화합니다.

        Args:
            logger_instance: 로그를 출력할 Logger. 미지정 시 모듈 로거 사용.
        """
        super().__init__()
        self._logger = logger_instance or logger
        self._start_times: Dict[str, float] = {}

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: Any,
        **kwargs: Any,
    ) -> None:
        """LLM 호출 시작 시각을 기록합니다."""
        run_id = str(kwargs.get("run_id", "default"))
        self._start_times[run_id] = time.perf_counter()

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: Any,
        **kwargs: Any,
    ) -> None:
        """Chat 모델 호출 시작 시각을 기록합니다."""
        run_id = str(kwargs.get("run_id", "default"))
        self._start_times[run_id] = time.perf_counter()

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """LLM 호출 종료 시 토큰 사용량, 소요 시간, 비용을 로깅합니다."""
        run_id = str(kwargs.get("run_id", "default"))
        start_time = self._start_times.pop(run_id, None)
        if start_time is not None:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
        else:
            duration_ms = 0.0

        usage = _extract_token_usage(response)
        model = _extract_model_name(response, **kwargs)

        record = build_cost_log_record(
            model=model,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            duration_ms=duration_ms,
            total_tokens=usage["total_tokens"],
        )

        self._logger.info("LLM call completed", extra=record)
