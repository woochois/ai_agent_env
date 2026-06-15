"""비즈니스 Tool Agent 공통 LLM 유틸리티.

모든 비즈니스 에이전트가 공유하는 LLM 호출 및 응답 파싱 헬퍼를 제공합니다.

- ``call_llm``: 통합 LLM 호출 유틸리티 (Model_Router를 통한 프로바이더 라우팅)
- ``parse_json_response``: LLM 응답 텍스트에서 JSON 객체 추출

Requirements: 6.1, 6.2, 6.3, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_TEMPERATURE = 0.0
_DEFAULT_MAX_TOKENS = 4096
_TIMEOUT_SECONDS = 120


# ---------------------------------------------------------------------------
# call_llm
# ---------------------------------------------------------------------------


async def call_llm(
    system_prompt: str,
    user_input: str,
    model: str = _DEFAULT_MODEL,
    temperature: float = _DEFAULT_TEMPERATURE,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> str:
    """통합 LLM 호출 유틸리티. Model_Router를 통해 적절한 프로바이더로 라우팅.

    Args:
        system_prompt: 시스템 프롬프트 (비어 있거나 공백만 있으면 ValueError).
        user_input: 사용자 입력 (비어 있거나 공백만 있으면 ValueError).
        model: 모델 식별자. None/빈 문자열일 경우 "gpt-4o-mini" 사용.
        temperature: 샘플링 온도 (0.0~2.0).
        max_tokens: 최대 생성 토큰 수 (1~128000).

    Returns:
        LLM 응답 컨텐츠 텍스트.

    Raises:
        ValueError: 입력 검증 실패 시 (빈 프롬프트, 온도/토큰 범위 초과).
        RuntimeError: 프로바이더 호출 실패 시 (모델명, 프로바이더명, 원본 에러 포함).
        TimeoutError: 120초 내 응답 없을 시.

    Requirements: 6.1, 6.2, 6.3, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11
    """
    # --- Input validation (Req 6.8) ---
    if not system_prompt or not system_prompt.strip():
        raise ValueError("system_prompt must be a non-empty string (not empty or whitespace-only)")

    if not user_input or not user_input.strip():
        raise ValueError("user_input must be a non-empty string (not empty or whitespace-only)")

    # --- Default model handling (Req 6.5) ---
    if not model or not model.strip():
        model = _DEFAULT_MODEL

    # --- Temperature validation (Req 6.9) ---
    if temperature < 0.0 or temperature > 2.0:
        raise ValueError(
            f"temperature must be between 0.0 and 2.0 (inclusive), got {temperature}"
        )

    # --- Max tokens validation (Req 6.10) ---
    if max_tokens < 1 or max_tokens > 128000:
        raise ValueError(
            f"max_tokens must be between 1 and 128000 (inclusive), got {max_tokens}"
        )

    # --- Construct messages (Req 6.3) ---
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input),
    ]

    # --- Get router and invoke (Req 6.3, 6.6) ---
    from app.framework.model_router import get_model_router

    router = get_model_router()

    try:
        result = await asyncio.wait_for(
            router.ainvoke(model, messages, temperature=temperature, max_tokens=max_tokens),
            timeout=_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise TimeoutError(
            f"LLM invocation timed out after {_TIMEOUT_SECONDS} seconds for model '{model}'"
        )
    except RuntimeError:
        # ModelRouter already wraps provider exceptions as RuntimeError
        raise
    except Exception as exc:
        raise RuntimeError(
            f"LLM invocation failed for model '{model}': "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    return result


# ---------------------------------------------------------------------------
# parse_json_response
# ---------------------------------------------------------------------------


def parse_json_response(response_text: str) -> dict | None:
    """LLM 응답 텍스트에서 JSON 객체를 추출하여 파싱합니다.

    추출 전략:
        1. ```json ... ``` 또는 ``` ... ``` 코드 블록 내부의 JSON을 파싱
        2. 코드 블록이 없거나 파싱 실패 시 전체 응답을 JSON으로 파싱
        3. 모두 실패하면 None 반환

    Args:
        response_text: LLM이 반환한 원시 텍스트.

    Returns:
        파싱된 dict 또는 None.
    """
    # 1. 코드 블록에서 JSON 추출
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response_text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 2. 전체를 JSON으로 파싱
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        return None
