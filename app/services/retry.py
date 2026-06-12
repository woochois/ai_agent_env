"""연결 재시도 유틸리티 모듈.

Database, Elasticsearch 등 외부 서비스 연결 실패 시 일정 간격으로
재시도하는 비동기 유틸리티를 제공합니다.

동작: 최대 max_retries회 연결을 시도하며, 각 시도 사이에 interval_seconds초
대기합니다. 모든 시도가 실패하면 에러 로그를 기록하고 None을 반환합니다.

Requirements: 5.5, 6.5
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Awaitable, Callable, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")

# connect_fn은 동기 또는 비동기(코루틴) 호출 가능 객체를 모두 허용합니다.
ConnectFn = Callable[[], Union[T, Awaitable[T]]]


async def connect_with_retry(
    connect_fn: ConnectFn,
    service_name: str,
    max_retries: int = 3,
    interval_seconds: float = 5.0,
) -> Optional[T]:
    """연결 함수를 재시도하며 호출합니다.

    최대 ``max_retries``회 ``connect_fn``을 호출합니다. 각 시도가 실패(예외 발생)하면
    마지막 시도가 아닌 한 ``interval_seconds``초 대기 후 다시 시도합니다.
    모든 시도가 실패하면 에러 로그를 기록하고 ``None``을 반환합니다.

    연결 흐름 (max_retries=3 기준):
        1차 시도 실패 → interval_seconds 대기 → 2차 시도 실패 →
        interval_seconds 대기 → 3차 시도 실패 → 에러 로그 → None 반환

    Args:
        connect_fn: 연결을 시도하는 호출 가능 객체. 동기 함수 또는 코루틴 함수
            모두 지원합니다. 실패 시 예외를 발생시켜야 합니다.
        service_name: 로그에 표시할 서비스 이름 (예: "database", "elasticsearch").
        max_retries: 최대 시도 횟수. 기본값 3.
        interval_seconds: 각 시도 사이의 대기 시간(초). 기본값 5.0.

    Returns:
        연결에 성공하면 ``connect_fn``의 반환값, 모든 시도가 실패하면 ``None``.
    """
    last_error: Optional[BaseException] = None

    for attempt in range(1, max_retries + 1):
        logger.info(
            "Attempting to connect to %s (attempt %d/%d)",
            service_name,
            attempt,
            max_retries,
            extra={
                "service": service_name,
                "attempt": attempt,
                "max_retries": max_retries,
            },
        )

        try:
            result = connect_fn()
            if inspect.isawaitable(result):
                result = await result
            logger.info(
                "Successfully connected to %s on attempt %d/%d",
                service_name,
                attempt,
                max_retries,
                extra={
                    "service": service_name,
                    "attempt": attempt,
                    "max_retries": max_retries,
                },
            )
            return result
        except Exception as exc:  # noqa: BLE001 - 모든 연결 오류를 재시도 대상으로 처리
            last_error = exc
            logger.warning(
                "Failed to connect to %s on attempt %d/%d: %s",
                service_name,
                attempt,
                max_retries,
                exc,
                extra={
                    "service": service_name,
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "error": str(exc),
                },
            )

            # 마지막 시도가 아니라면 다음 시도 전 대기
            if attempt < max_retries:
                await asyncio.sleep(interval_seconds)

    logger.error(
        "All %d connection attempts to %s failed. Last error: %s",
        max_retries,
        service_name,
        last_error,
        extra={
            "service": service_name,
            "max_retries": max_retries,
            "error": str(last_error) if last_error is not None else None,
        },
    )
    return None
