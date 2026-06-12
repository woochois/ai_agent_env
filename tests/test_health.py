"""app/health.py 단위 테스트.

헬스체크 엔드포인트의 동작을 검증합니다:
- DB, ES 모두 정상 → "healthy"
- 하나만 실패 → "degraded"
- 모두 실패 → "unhealthy"
- uptime_seconds 포함
- 응답 구조가 HealthResponse 스키마와 일치

Requirements: 2.4, 2.7
"""

from __future__ import annotations

import os
import time
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# 테스트 환경 변수 설정 (import 전에 설정)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("ELASTICSEARCH_URL", "http://localhost:9200")

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import create_app  # noqa: E402


@pytest.fixture
def mock_db_healthy():
    """정상 연결된 Database mock."""
    mock = AsyncMock()
    mock.health_check = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_db_unhealthy():
    """연결 실패 Database mock."""
    mock = AsyncMock()
    mock.health_check = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def mock_es_healthy():
    """정상 연결된 Elasticsearch mock."""
    mock = AsyncMock()
    mock.is_healthy = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_es_unhealthy():
    """연결 실패 Elasticsearch mock."""
    mock = AsyncMock()
    mock.is_healthy = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def test_app():
    """테스트용 FastAPI 앱을 생성합니다 (lifespan 없이)."""
    with (
        patch("app.main.Database") as mock_db_class,
        patch("app.main.ElasticsearchClient") as mock_es_class,
    ):
        mock_db = AsyncMock()
        mock_db.connect = AsyncMock(return_value=True)
        mock_db.disconnect = AsyncMock()
        mock_db_class.return_value = mock_db

        mock_es = AsyncMock()
        mock_es.connect = AsyncMock(return_value=mock_es)
        mock_es.close = AsyncMock()
        mock_es_class.return_value = mock_es

        app = create_app()
        yield app


class TestHealthEndpointStatus:
    """헬스체크 상태 판단 테스트."""

    @pytest.mark.asyncio
    async def test_healthy_when_both_connected(
        self, test_app, mock_db_healthy, mock_es_healthy
    ):
        """DB, ES 모두 정상이면 'healthy'를 반환합니다."""
        with (
            patch("app.main.get_db", return_value=mock_db_healthy),
            patch("app.main.get_es", return_value=mock_es_healthy),
            patch("app.main.get_start_time", return_value=time.time() - 10.0),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["elasticsearch"] == "connected"

    @pytest.mark.asyncio
    async def test_degraded_when_db_fails(
        self, test_app, mock_db_unhealthy, mock_es_healthy
    ):
        """DB만 실패하면 'degraded'를 반환합니다."""
        with (
            patch("app.main.get_db", return_value=mock_db_unhealthy),
            patch("app.main.get_es", return_value=mock_es_healthy),
            patch("app.main.get_start_time", return_value=time.time() - 5.0),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "disconnected"
        assert data["elasticsearch"] == "connected"

    @pytest.mark.asyncio
    async def test_degraded_when_es_fails(
        self, test_app, mock_db_healthy, mock_es_unhealthy
    ):
        """ES만 실패하면 'degraded'를 반환합니다."""
        with (
            patch("app.main.get_db", return_value=mock_db_healthy),
            patch("app.main.get_es", return_value=mock_es_unhealthy),
            patch("app.main.get_start_time", return_value=time.time() - 5.0),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "connected"
        assert data["elasticsearch"] == "disconnected"

    @pytest.mark.asyncio
    async def test_unhealthy_when_both_fail(
        self, test_app, mock_db_unhealthy, mock_es_unhealthy
    ):
        """DB, ES 모두 실패하면 'unhealthy'를 반환합니다."""
        with (
            patch("app.main.get_db", return_value=mock_db_unhealthy),
            patch("app.main.get_es", return_value=mock_es_unhealthy),
            patch("app.main.get_start_time", return_value=time.time() - 5.0),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert data["elasticsearch"] == "disconnected"


class TestHealthEndpointResponse:
    """헬스체크 응답 구조 테스트."""

    @pytest.mark.asyncio
    async def test_response_contains_uptime_seconds(
        self, test_app, mock_db_healthy, mock_es_healthy
    ):
        """응답에 uptime_seconds 필드가 포함됩니다."""
        start = time.time() - 42.5
        with (
            patch("app.main.get_db", return_value=mock_db_healthy),
            patch("app.main.get_es", return_value=mock_es_healthy),
            patch("app.main.get_start_time", return_value=start),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

        data = response.json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))
        # uptime should be approximately 42.5 seconds
        assert data["uptime_seconds"] >= 42.0

    @pytest.mark.asyncio
    async def test_response_matches_health_response_schema(
        self, test_app, mock_db_healthy, mock_es_healthy
    ):
        """응답이 HealthResponse 스키마의 모든 필드를 포함합니다."""
        with (
            patch("app.main.get_db", return_value=mock_db_healthy),
            patch("app.main.get_es", return_value=mock_es_healthy),
            patch("app.main.get_start_time", return_value=time.time() - 1.0),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

        data = response.json()
        expected_fields = {"status", "database", "elasticsearch", "uptime_seconds"}
        assert set(data.keys()) == expected_fields

    @pytest.mark.asyncio
    async def test_status_values_are_valid(
        self, test_app, mock_db_healthy, mock_es_healthy
    ):
        """status 필드가 유효한 값만 포함합니다."""
        with (
            patch("app.main.get_db", return_value=mock_db_healthy),
            patch("app.main.get_es", return_value=mock_es_healthy),
            patch("app.main.get_start_time", return_value=time.time() - 1.0),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

        data = response.json()
        assert data["status"] in {"healthy", "degraded", "unhealthy"}
        assert data["database"] in {"connected", "disconnected"}
        assert data["elasticsearch"] in {"connected", "disconnected"}


class TestHealthEndpointEdgeCases:
    """헬스체크 엣지 케이스 테스트."""

    @pytest.mark.asyncio
    async def test_handles_db_exception_gracefully(self, test_app, mock_es_healthy):
        """DB 헬스체크에서 예외가 발생해도 정상 응답합니다."""
        mock_db = AsyncMock()
        mock_db.health_check = AsyncMock(side_effect=RuntimeError("DB 연결 오류"))

        with (
            patch("app.main.get_db", return_value=mock_db),
            patch("app.main.get_es", return_value=mock_es_healthy),
            patch("app.main.get_start_time", return_value=time.time() - 1.0),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["database"] == "disconnected"
        assert data["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_handles_es_exception_gracefully(self, test_app, mock_db_healthy):
        """ES 헬스체크에서 예외가 발생해도 정상 응답합니다."""
        mock_es = AsyncMock()
        mock_es.is_healthy = AsyncMock(side_effect=ConnectionError("ES 연결 오류"))

        with (
            patch("app.main.get_db", return_value=mock_db_healthy),
            patch("app.main.get_es", return_value=mock_es),
            patch("app.main.get_start_time", return_value=time.time() - 1.0),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["elasticsearch"] == "disconnected"
        assert data["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_handles_none_services(self, test_app):
        """DB/ES 인스턴스가 None일 때 'unhealthy'를 반환합니다."""
        with (
            patch("app.main.get_db", return_value=None),
            patch("app.main.get_es", return_value=None),
            patch("app.main.get_start_time", return_value=time.time() - 1.0),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert data["elasticsearch"] == "disconnected"
