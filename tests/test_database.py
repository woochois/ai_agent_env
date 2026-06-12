"""app/services/database.py 단위 테스트.

PostgreSQL 비동기 연결 관리 모듈의 URL 정규화, 재시도 적용 연결,
헬스체크 동작을 검증합니다. 실제 DB 없이 동작하도록 SQLAlchemy 엔진을
스텁(stub)으로 대체합니다.

Requirements: 6.3, 6.4, 6.5
"""

from __future__ import annotations

import pytest

from app.services.database import Database, _normalize_async_url


class _FakeConn:
    """async 컨텍스트 매니저로 동작하는 가짜 연결."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def __aenter__(self) -> "_FakeConn":
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def execute(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("connection refused")
        return None


class _FakeEngine:
    """SELECT 1 실행 및 dispose를 흉내내는 가짜 엔진."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.dispose_called = False
        self.connect_calls = 0

    def connect(self) -> _FakeConn:
        self.connect_calls += 1
        return _FakeConn(fail=self.fail)

    async def dispose(self) -> None:
        self.dispose_called = True


# --- URL 정규화 테스트 ---


def test_normalize_postgresql_scheme_converted_to_asyncpg():
    """postgresql:// 스킴이 postgresql+asyncpg://로 변환된다."""
    url = "postgresql://agent_user:agent_password@db:5432/agent_db"
    result = _normalize_async_url(url)
    assert result == "postgresql+asyncpg://agent_user:agent_password@db:5432/agent_db"


def test_normalize_already_async_url_unchanged():
    """이미 asyncpg 드라이버가 명시된 URL은 변경되지 않는다."""
    url = "postgresql+asyncpg://u:p@db:5432/x"
    assert _normalize_async_url(url) == url


def test_normalize_postgres_short_scheme_converted():
    """postgres:// 단축 스킴도 asyncpg URL로 변환된다."""
    url = "postgres://u:p@db:5432/x"
    assert _normalize_async_url(url) == "postgresql+asyncpg://u:p@db:5432/x"


def test_init_uses_explicit_url():
    """명시적으로 전달한 URL을 정규화하여 사용한다."""
    db = Database("postgresql://u:p@host:5432/dbname")
    assert db.database_url == "postgresql+asyncpg://u:p@host:5432/dbname"
    assert db.engine is None
    assert db.session_factory is None


# --- connect 테스트 ---


@pytest.mark.asyncio
async def test_connect_success(monkeypatch):
    """엔진 연결 검증이 성공하면 connect는 True를 반환하고 세션 팩토리가 설정된다."""
    fake_engine = _FakeEngine(fail=False)

    monkeypatch.setattr(
        "app.services.database.create_async_engine",
        lambda *a, **k: fake_engine,
    )
    monkeypatch.setattr(
        "app.services.database.async_sessionmaker",
        lambda *a, **k: object(),
    )

    db = Database("postgresql://u:p@db:5432/x")
    result = await db.connect(max_retries=3, interval_seconds=0)

    assert result is True
    assert db.engine is fake_engine
    assert db.session_factory is not None
    assert fake_engine.connect_calls == 1


@pytest.mark.asyncio
async def test_connect_failure_returns_false_and_disposes(monkeypatch):
    """연결 검증이 계속 실패하면 connect는 False를 반환하고 엔진을 정리한다."""
    fake_engine = _FakeEngine(fail=True)

    monkeypatch.setattr(
        "app.services.database.create_async_engine",
        lambda *a, **k: fake_engine,
    )
    monkeypatch.setattr(
        "app.services.database.async_sessionmaker",
        lambda *a, **k: object(),
    )

    db = Database("postgresql://u:p@db:5432/x")
    result = await db.connect(max_retries=3, interval_seconds=0)

    assert result is False
    # 3회 시도 후 실패
    assert fake_engine.connect_calls == 3
    # 실패 시 dispose 호출로 리소스 정리, 엔진 참조 해제
    assert fake_engine.dispose_called is True
    assert db.engine is None
    assert db.session_factory is None


# --- health_check 테스트 ---


@pytest.mark.asyncio
async def test_health_check_no_engine_returns_false():
    """엔진이 없으면 헬스체크는 False를 반환한다."""
    db = Database("postgresql://u:p@db:5432/x")
    assert await db.health_check() is False


@pytest.mark.asyncio
async def test_health_check_success():
    """엔진 쿼리가 성공하면 헬스체크는 True를 반환한다."""
    db = Database("postgresql://u:p@db:5432/x")
    db.engine = _FakeEngine(fail=False)
    assert await db.health_check() is True


@pytest.mark.asyncio
async def test_health_check_failure_returns_false():
    """엔진 쿼리가 실패하면 헬스체크는 False를 반환한다."""
    db = Database("postgresql://u:p@db:5432/x")
    db.engine = _FakeEngine(fail=True)
    assert await db.health_check() is False


@pytest.mark.asyncio
async def test_disconnect_disposes_engine():
    """disconnect는 엔진을 dispose하고 참조를 해제한다."""
    db = Database("postgresql://u:p@db:5432/x")
    fake_engine = _FakeEngine()
    db.engine = fake_engine
    db.session_factory = object()

    await db.disconnect()

    assert fake_engine.dispose_called is True
    assert db.engine is None
    assert db.session_factory is None
