"""Property-Based Test: 연결 재시도 일관성.

# Feature: docker-ai-agent-dev-env, Property 2: 연결 재시도 일관성

For any 연결 실패 상황(Database 또는 Elasticsearch)에서, 재시도 모듈은
정확히 3회 재시도를 수행하고, 각 시도 간 5초 간격을 유지하며,
모든 재시도 실패 시 에러 상태를 로그에 기록해야 한다.

**Validates: Requirements 5.5, 6.5**
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.retry import connect_with_retry


# --- Strategies ---

# 서비스 이름 생성 전략: 일반적인 서비스명 문자열
service_name_strategy = st.sampled_from([
    "database",
    "elasticsearch",
    "redis",
    "rabbitmq",
    "mongodb",
])

# 예외 메시지 생성 전략
error_message_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=100,
)

# 예외 유형 생성 전략
exception_type_strategy = st.sampled_from([
    ConnectionError,
    TimeoutError,
    OSError,
    RuntimeError,
    IOError,
])


@settings(max_examples=10)
@given(
    service_name=service_name_strategy,
    error_message=error_message_strategy,
    exception_type=exception_type_strategy,
)
def test_retry_exactly_3_attempts_on_failure(
    service_name: str,
    error_message: str,
    exception_type: type,
):
    """Property 2: 연결 재시도 일관성 - 정확히 3회 재시도 수행.

    항상 실패하는 연결 함수에 대해 connect_with_retry가 정확히
    max_retries(3)회 호출되는지 검증한다.

    Validates: Requirements 5.5, 6.5
    """

    async def _run():
        # Arrange: 항상 실패하는 mock 연결 함수
        mock_connect = AsyncMock(side_effect=exception_type(error_message))

        # Act: asyncio.sleep을 패치하여 실제 대기 없이 테스트
        with patch("app.services.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await connect_with_retry(
                connect_fn=mock_connect,
                service_name=service_name,
                max_retries=3,
                interval_seconds=5.0,
            )

        # Assert: 정확히 3회 호출
        assert mock_connect.call_count == 3, (
            f"Expected exactly 3 attempts, got {mock_connect.call_count}"
        )
        # 모든 시도 실패 시 None 반환
        assert result is None

    asyncio.run(_run())


@settings(max_examples=10)
@given(
    service_name=service_name_strategy,
    error_message=error_message_strategy,
    exception_type=exception_type_strategy,
)
def test_retry_interval_5_seconds_between_attempts(
    service_name: str,
    error_message: str,
    exception_type: type,
):
    """Property 2: 연결 재시도 일관성 - 각 시도 간 5초 간격 유지.

    재시도 사이에 asyncio.sleep(5.0)이 정확히 호출되는지 검증한다.
    3회 시도이므로 sleep은 2회 호출되어야 한다 (1→2 사이, 2→3 사이).

    Validates: Requirements 5.5, 6.5
    """

    async def _run():
        # Arrange
        mock_connect = AsyncMock(side_effect=exception_type(error_message))

        # Act
        with patch("app.services.retry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await connect_with_retry(
                connect_fn=mock_connect,
                service_name=service_name,
                max_retries=3,
                interval_seconds=5.0,
            )

        # Assert: sleep은 2회 호출 (마지막 시도 후에는 대기 없음)
        assert mock_sleep.call_count == 2, (
            f"Expected 2 sleep calls between 3 attempts, got {mock_sleep.call_count}"
        )
        # 각 sleep 호출이 정확히 5.0초인지 확인
        for call in mock_sleep.call_args_list:
            assert call.args[0] == 5.0, (
                f"Expected sleep interval of 5.0 seconds, got {call.args[0]}"
            )

    asyncio.run(_run())


@settings(max_examples=10)
@given(
    service_name=service_name_strategy,
    error_message=error_message_strategy,
    exception_type=exception_type_strategy,
)
def test_retry_error_log_on_all_failures(
    service_name: str,
    error_message: str,
    exception_type: type,
):
    """Property 2: 연결 재시도 일관성 - 모든 실패 시 에러 로그 기록.

    connect_with_retry가 모든 시도 실패 후 ERROR 레벨 로그를
    남기는지 검증한다.

    Validates: Requirements 5.5, 6.5
    """

    async def _run():
        # Arrange
        mock_connect = AsyncMock(side_effect=exception_type(error_message))

        # Act
        with patch("app.services.retry.asyncio.sleep", new_callable=AsyncMock):
            with patch("app.services.retry.logger") as mock_logger:
                await connect_with_retry(
                    connect_fn=mock_connect,
                    service_name=service_name,
                    max_retries=3,
                    interval_seconds=5.0,
                )

        # Assert: error 로그가 최소 1회 호출됨
        assert mock_logger.error.call_count >= 1, (
            "Expected at least one error log call after all retries failed"
        )
        # 에러 로그 메시지에 서비스명이 포함됨
        error_call_args = mock_logger.error.call_args
        # 위치 인자들에 service_name이 포함되어야 함
        format_args = error_call_args.args
        assert service_name in format_args, (
            f"Expected service name '{service_name}' in error log arguments, "
            f"got: {format_args}"
        )

    asyncio.run(_run())
