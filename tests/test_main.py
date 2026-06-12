"""app/main.py 단위 테스트.

FastAPI 앱 진입점의 핵심 기능을 검증합니다:
- 앱 인스턴스 생성 및 라우터 등록
- 전역 예외 핸들러 (HTTP 500 반환 + 서비스 계속 실행)
- 플레이스홀더 엔드포인트 동작
- Lifespan 이벤트 (DB/ES 연결 초기화)

Requirements: 2.3, 2.5, 8.3
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# 테스트 환경 변수 설정 (import 전에 설정)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("ELASTICSEARCH_URL", "http://localhost:9200")

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture
def test_app():
    """DB/ES 연결을 모킹한 테스트용 FastAPI 앱을 생성합니다."""
    with (
        patch("app.main.Database") as mock_db_class,
        patch("app.main.ElasticsearchClient") as mock_es_class,
    ):
        # Database mock
        mock_db = AsyncMock()
        mock_db.connect = AsyncMock(return_value=True)
        mock_db.health_check = AsyncMock(return_value=True)
        mock_db.disconnect = AsyncMock()
        mock_db_class.return_value = mock_db

        # ES mock
        mock_es = AsyncMock()
        mock_es.connect = AsyncMock(return_value=mock_es)
        mock_es.is_healthy = AsyncMock(return_value=True)
        mock_es.close = AsyncMock()
        mock_es_class.return_value = mock_es

        from app.main import create_app

        app = create_app()
        yield app


@pytest.fixture
async def client(test_app):
    """비동기 HTTP 테스트 클라이언트."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestAppCreation:
    """FastAPI 앱 인스턴스 생성 테스트."""

    def test_app_has_correct_title(self, test_app):
        """앱 타이틀이 올바르게 설정되는지 확인합니다."""
        assert test_app.title == "AI Agent Server"

    def test_app_has_correct_version(self, test_app):
        """앱 버전이 올바르게 설정되는지 확인합니다."""
        assert test_app.version == "0.1.0"

    def test_app_registers_health_endpoint(self, test_app):
        """GET /health 엔드포인트가 등록되는지 확인합니다."""
        paths = [route.path for route in test_app.routes if hasattr(route, "path")]
        assert "/health" in paths

    def test_app_registers_agent_chat_endpoint(self, test_app):
        """POST /agent/chat 엔드포인트가 등록되는지 확인합니다."""
        paths = [route.path for route in test_app.routes if hasattr(route, "path")]
        assert "/agent/chat" in paths

    def test_app_registers_agent_history_endpoint(self, test_app):
        """GET /agent/history 엔드포인트가 등록되는지 확인합니다."""
        paths = [route.path for route in test_app.routes if hasattr(route, "path")]
        assert "/agent/history" in paths

    def test_app_registers_docs_endpoint(self, test_app):
        """/docs (Swagger UI) 엔드포인트가 자동 등록되는지 확인합니다."""
        paths = [route.path for route in test_app.routes if hasattr(route, "path")]
        assert "/docs" in paths


class TestGlobalExceptionHandler:
    """전역 예외 핸들러 테스트."""

    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_500(self, test_app):
        """처리되지 않은 예외 발생 시 HTTP 500을 반환합니다."""

        @test_app.get("/test-error")
        async def raise_error():
            raise RuntimeError("테스트 예외")

        transport = ASGITransport(app=test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/test-error")

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_error_response_structure(self, test_app):
        """예외 응답이 ErrorResponse 스키마를 따릅니다."""

        @test_app.get("/test-error-structure")
        async def raise_error():
            raise ValueError("구조 테스트")

        transport = ASGITransport(app=test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/test-error-structure")

        data = response.json()
        assert "error" in data
        assert "message" in data
        assert "request_id" in data
        assert data["error"] == "ValueError"
        assert data["message"] == "내부 서버 오류가 발생했습니다."

    @pytest.mark.asyncio
    async def test_exception_handler_includes_request_id(self, test_app):
        """예외 응답에 유효한 request_id가 포함됩니다."""

        @test_app.get("/test-request-id")
        async def raise_error():
            raise TypeError("request_id 테스트")

        transport = ASGITransport(app=test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/test-request-id")

        data = response.json()
        # UUID format check
        assert len(data["request_id"]) == 36
        assert data["request_id"].count("-") == 4

    @pytest.mark.asyncio
    async def test_service_continues_after_exception(self, test_app):
        """예외 발생 후에도 서비스가 계속 실행됩니다."""

        @test_app.get("/test-continue-error")
        async def raise_error():
            raise RuntimeError("첫 번째 예외")

        @test_app.get("/test-continue-ok")
        async def ok_endpoint():
            return {"status": "ok"}

        transport = ASGITransport(app=test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 예외가 발생하는 엔드포인트 호출
            error_response = await ac.get("/test-continue-error")
            assert error_response.status_code == 500

            # 이후 정상 엔드포인트가 작동하는지 확인
            ok_response = await ac.get("/test-continue-ok")
            assert ok_response.status_code == 200
            assert ok_response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_detail_hidden_when_not_debug_mode(self, test_app):
        """DEBUG_MODE가 아닐 때 detail 필드가 None입니다."""

        @test_app.get("/test-no-detail")
        async def raise_error():
            raise RuntimeError("비밀 정보")

        transport = ASGITransport(app=test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/test-no-detail")

        data = response.json()
        assert data["detail"] is None


class TestPlaceholderEndpoints:
    """플레이스홀더 엔드포인트 테스트."""

    @pytest.mark.asyncio
    async def test_agent_chat_returns_placeholder_response(self, test_app):
        """/agent/chat 플레이스홀더가 올바른 응답을 반환합니다."""
        transport = ASGITransport(app=test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/agent/chat",
                json={"message": "안녕하세요"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "session_id" in data
        assert data["sources"] == []

    @pytest.mark.asyncio
    async def test_agent_chat_uses_provided_session_id(self, test_app):
        """제공된 session_id가 응답에 반영됩니다."""
        transport = ASGITransport(app=test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/agent/chat",
                json={"message": "테스트", "session_id": "my-session-123"},
            )

        data = response.json()
        assert data["session_id"] == "my-session-123"

    @pytest.mark.asyncio
    async def test_agent_chat_generates_session_id_if_not_provided(self, test_app):
        """session_id가 없으면 자동 생성됩니다."""
        transport = ASGITransport(app=test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/agent/chat",
                json={"message": "테스트"},
            )

        data = response.json()
        assert data["session_id"] is not None
        assert len(data["session_id"]) > 0

    @pytest.mark.asyncio
    async def test_agent_history_returns_empty_list(self, test_app):
        """/agent/history 플레이스홀더가 빈 메시지 목록을 반환합니다."""
        transport = ASGITransport(app=test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/agent/history")

        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == []

    @pytest.mark.asyncio
    async def test_agent_history_accepts_session_id_param(self, test_app):
        """/agent/history가 session_id 쿼리 파라미터를 수용합니다."""
        transport = ASGITransport(app=test_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/agent/history?session_id=test-session")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session"


class TestHelperFunctions:
    """헬퍼 함수 테스트."""

    def test_get_start_time_returns_float(self):
        """get_start_time이 float을 반환합니다."""
        from app.main import get_start_time

        result = get_start_time()
        assert isinstance(result, float)
