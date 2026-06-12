"""Property 7: 예외 처리 복원력 Property-Based Test.

처리되지 않은 예외(예외 유형, 메시지 내용과 무관하게)가 Agent_Server에서 발생하면,
해당 요청은 HTTP 500 응답을 반환하고, 예외 정보가 로그에 기록되며,
서버 프로세스는 중단되지 않고 후속 요청을 처리할 수 있어야 한다.

**Validates: Requirements 2.5**

# Feature: docker-ai-agent-dev-env, Property 7: 예외 처리 복원력
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from httpx import ASGITransport, AsyncClient

# 테스트 환경 변수 설정 (import 전에 설정)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("ELASTICSEARCH_URL", "http://localhost:9200")

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import create_app  # noqa: E402


# --- Strategies ---

# 다양한 예외 유형 생성
EXCEPTION_TYPES = [
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
    IOError,
    OSError,
    IndexError,
    ZeroDivisionError,
    OverflowError,
    MemoryError,
    NotImplementedError,
    PermissionError,
    TimeoutError,
    ConnectionError,
    FileNotFoundError,
    UnicodeError,
    ArithmeticError,
    LookupError,
    # Note: StopIteration은 async 함수 내에서 Python 런타임이 RuntimeError로
    # 변환하므로 (PEP 479) 제외합니다. 이는 Python의 정상 동작입니다.
]

exception_type_strategy = st.sampled_from(EXCEPTION_TYPES)

# 다양한 예외 메시지 생성 (빈 문자열, 유니코드, 특수문자 포함)
exception_message_strategy = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "S", "Z"),
    ),
    min_size=0,
    max_size=200,
)


# --- Fixtures ---


def _create_test_app():
    """DB/ES 연결을 모킹한 테스트용 FastAPI 앱을 생성합니다."""
    with (
        patch("app.main.Database") as mock_db_class,
        patch("app.main.ElasticsearchClient") as mock_es_class,
    ):
        mock_db = AsyncMock()
        mock_db.connect = AsyncMock(return_value=True)
        mock_db.health_check = AsyncMock(return_value=True)
        mock_db.disconnect = AsyncMock()
        mock_db_class.return_value = mock_db

        mock_es = AsyncMock()
        mock_es.connect = AsyncMock(return_value=mock_es)
        mock_es.is_healthy = AsyncMock(return_value=True)
        mock_es.close = AsyncMock()
        mock_es_class.return_value = mock_es

        app = create_app()
        return app


# 모듈 레벨에서 앱을 1회만 생성 (Hypothesis가 반복 호출하므로)
_test_app = _create_test_app()

# 테스트마다 고유한 엔드포인트 경로를 위한 카운터
_endpoint_counter = 0


def _get_unique_path():
    """고유한 테스트 엔드포인트 경로를 생성합니다."""
    global _endpoint_counter
    _endpoint_counter += 1
    return f"/test-prop7-error-{_endpoint_counter}"


# --- Property Tests ---


class TestExceptionResilienceProperty:
    """Property 7: 예외 처리 복원력 Property-Based Tests.

    **Validates: Requirements 2.5**
    """

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        exc_type=exception_type_strategy,
        exc_message=exception_message_strategy,
    )
    @pytest.mark.asyncio
    async def test_any_exception_returns_http_500(
        self, exc_type: type, exc_message: str
    ):
        """어떤 예외 유형과 메시지이든 HTTP 500을 반환한다.

        **Validates: Requirements 2.5**
        """
        path = _get_unique_path()

        @_test_app.get(path)
        async def raise_error():
            raise exc_type(exc_message)

        transport = ASGITransport(app=_test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(path)

        assert response.status_code == 500, (
            f"Expected 500 for {exc_type.__name__}('{exc_message}'), "
            f"got {response.status_code}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        exc_type=exception_type_strategy,
        exc_message=exception_message_strategy,
    )
    @pytest.mark.asyncio
    async def test_error_response_follows_schema(
        self, exc_type: type, exc_message: str
    ):
        """에러 응답이 ErrorResponse 스키마를 따른다 (error, message, detail, request_id).

        **Validates: Requirements 2.5**
        """
        path = _get_unique_path()

        @_test_app.get(path)
        async def raise_error():
            raise exc_type(exc_message)

        transport = ASGITransport(app=_test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(path)

        data = response.json()

        # ErrorResponse 스키마 필수 필드 존재 확인
        assert "error" in data, f"'error' field missing for {exc_type.__name__}"
        assert "message" in data, f"'message' field missing for {exc_type.__name__}"
        assert "detail" in data, f"'detail' field missing for {exc_type.__name__}"
        assert "request_id" in data, f"'request_id' field missing for {exc_type.__name__}"

        # error 필드가 예외 유형명과 일치
        assert data["error"] == exc_type.__name__, (
            f"Expected error='{exc_type.__name__}', got '{data['error']}'"
        )

        # message 필드가 비어있지 않은 문자열
        assert isinstance(data["message"], str) and len(data["message"]) > 0

        # request_id가 유효한 UUID 형식 (36자, 하이픈 4개)
        assert len(data["request_id"]) == 36, (
            f"request_id length should be 36, got {len(data['request_id'])}"
        )
        assert data["request_id"].count("-") == 4, (
            f"request_id should have 4 hyphens, got {data['request_id'].count('-')}"
        )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        exc_type=exception_type_strategy,
        exc_message=exception_message_strategy,
    )
    @pytest.mark.asyncio
    async def test_server_continues_after_exception(
        self, exc_type: type, exc_message: str
    ):
        """예외 발생 후에도 서버가 후속 요청을 처리할 수 있다.

        **Validates: Requirements 2.5**
        """
        error_path = _get_unique_path()
        ok_path = _get_unique_path()

        @_test_app.get(error_path)
        async def raise_error():
            raise exc_type(exc_message)

        @_test_app.get(ok_path)
        async def ok_endpoint():
            return {"status": "ok"}

        transport = ASGITransport(app=_test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 예외를 발생시키는 요청
            error_response = await ac.get(error_path)
            assert error_response.status_code == 500

            # 후속 정상 요청이 성공하는지 확인
            ok_response = await ac.get(ok_path)
            assert ok_response.status_code == 200, (
                f"Server failed to respond after {exc_type.__name__}('{exc_message}'). "
                f"Got status {ok_response.status_code}"
            )
            assert ok_response.json() == {"status": "ok"}
