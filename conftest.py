"""pytest 공유 fixture 설정.

FastAPI TestClient, mock 서비스 인스턴스 등 테스트 전반에서 재사용할 수 있는
fixture를 정의합니다.

Requirements: 8.1, 8.2
"""

from __future__ import annotations

import os
import time
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# 테스트 환경 변수 설정 (모든 테스트 모듈에서 import 전에 적용)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("ELASTICSEARCH_URL", "http://localhost:9200")


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """각 테스트 전후로 Settings 캐시를 정리합니다."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Mock 서비스 Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """정상 연결된 Database AsyncMock.

    connect, disconnect, health_check 메서드를 포함합니다.
    """
    mock = AsyncMock()
    mock.connect = AsyncMock(return_value=True)
    mock.disconnect = AsyncMock()
    mock.health_check = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_db_unhealthy():
    """연결 실패 상태의 Database AsyncMock."""
    mock = AsyncMock()
    mock.connect = AsyncMock(return_value=False)
    mock.disconnect = AsyncMock()
    mock.health_check = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def mock_es():
    """정상 연결된 ElasticsearchClient AsyncMock.

    connect, close, is_healthy 메서드를 포함합니다.
    """
    mock = AsyncMock()
    mock.connect = AsyncMock(return_value=mock)
    mock.close = AsyncMock()
    mock.is_healthy = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_es_unhealthy():
    """연결 실패 상태의 ElasticsearchClient AsyncMock."""
    mock = AsyncMock()
    mock.connect = AsyncMock(return_value=None)
    mock.close = AsyncMock()
    mock.is_healthy = AsyncMock(return_value=False)
    return mock


# ---------------------------------------------------------------------------
# FastAPI App Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_app():
    """테스트용 FastAPI 앱을 생성합니다.

    Database와 ElasticsearchClient를 mock으로 대체하여
    실제 외부 서비스 연결 없이 앱을 테스트할 수 있습니다.
    """
    with (
        patch("app.main.Database") as mock_db_class,
        patch("app.main.ElasticsearchClient") as mock_es_class,
    ):
        mock_db_inst = AsyncMock()
        mock_db_inst.connect = AsyncMock(return_value=True)
        mock_db_inst.disconnect = AsyncMock()
        mock_db_inst.health_check = AsyncMock(return_value=True)
        mock_db_class.return_value = mock_db_inst

        mock_es_inst = AsyncMock()
        mock_es_inst.connect = AsyncMock(return_value=mock_es_inst)
        mock_es_inst.close = AsyncMock()
        mock_es_inst.is_healthy = AsyncMock(return_value=True)
        mock_es_class.return_value = mock_es_inst

        from app.main import create_app

        app = create_app()
        yield app


@pytest.fixture
async def async_client(test_app):
    """httpx AsyncClient fixture.

    테스트에서 HTTP 요청을 보낼 수 있는 비동기 클라이언트를 제공합니다.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
