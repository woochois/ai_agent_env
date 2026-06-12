"""PostgreSQL 비동기 연결 관리 모듈.

SQLAlchemy 2.0의 비동기 엔진과 asyncpg 드라이버를 사용하여 PostgreSQL에
연결합니다. DATABASE_URL 환경 변수로 연결을 설정하며, 연결 시 재시도
유틸리티(``connect_with_retry``)를 적용하고 헬스체크용 연결 상태 확인
메서드를 제공합니다.

DATABASE_URL은 ``.env.example`` 기준으로 ``postgresql://`` 스킴을 사용하므로,
비동기 엔진을 위해 ``postgresql+asyncpg://`` 스킴으로 변환합니다.

Requirements: 6.3, 6.4, 6.5
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.services.retry import connect_with_retry

logger = logging.getLogger(__name__)


def _normalize_async_url(database_url: str) -> str:
    """DATABASE_URL을 asyncpg 드라이버용 비동기 URL로 변환합니다.

    ``.env.example``의 DATABASE_URL은 ``postgresql://`` 스킴을 사용하지만,
    SQLAlchemy 비동기 엔진은 ``postgresql+asyncpg://`` 스킴이 필요합니다.
    이미 드라이버가 지정된 경우(``postgresql+asyncpg://``)에는 그대로 둡니다.

    Args:
        database_url: 원본 DATABASE_URL 문자열.

    Returns:
        asyncpg 드라이버를 사용하는 정규화된 연결 URL.
    """
    if database_url.startswith("postgresql+"):
        # 이미 드라이버가 명시된 경우 변경하지 않음
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgres://"):
        # 일부 환경에서 사용하는 postgres:// 스킴도 지원
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return database_url


class Database:
    """PostgreSQL 비동기 연결을 관리하는 클래스.

    SQLAlchemy 비동기 엔진과 세션 팩토리를 보유하며, 재시도 로직을 적용한
    연결 초기화와 헬스체크용 연결 상태 확인 메서드를 제공합니다.

    Attributes:
        database_url: asyncpg 드라이버용으로 정규화된 연결 URL.
        engine: SQLAlchemy 비동기 엔진. 연결 전에는 None.
        session_factory: AsyncSession 팩토리. 연결 전에는 None.
    """

    def __init__(self, database_url: Optional[str] = None) -> None:
        """Database 인스턴스를 초기화합니다.

        Args:
            database_url: PostgreSQL 연결 URL. None이면 설정(get_settings)의
                DATABASE_URL을 사용합니다.
        """
        if database_url is None:
            database_url = get_settings().DATABASE_URL
        self.database_url = _normalize_async_url(database_url)
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    async def connect(
        self,
        max_retries: int = 3,
        interval_seconds: float = 5.0,
    ) -> bool:
        """재시도 로직을 적용하여 데이터베이스에 연결합니다.

        비동기 엔진을 생성하고 실제 연결이 가능한지 검증합니다. 연결 검증은
        ``connect_with_retry``를 통해 최대 ``max_retries``회, 각 시도 사이
        ``interval_seconds``초 간격으로 재시도됩니다.

        Args:
            max_retries: 최대 연결 시도 횟수. 기본값 3.
            interval_seconds: 각 시도 사이의 대기 시간(초). 기본값 5.0.

        Returns:
            연결에 성공하면 True, 모든 재시도가 실패하면 False.
        """
        # 비동기 엔진 및 세션 팩토리 생성 (실제 연결은 lazy하게 발생)
        self.engine = create_async_engine(
            self.database_url,
            pool_pre_ping=True,
            echo=False,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async def _verify_connection() -> AsyncEngine:
            """실제 연결을 열어 데이터베이스 접속 가능 여부를 검증합니다."""
            assert self.engine is not None
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return self.engine

        result = await connect_with_retry(
            _verify_connection,
            service_name="database",
            max_retries=max_retries,
            interval_seconds=interval_seconds,
        )

        if result is None:
            logger.error(
                "Database connection failed after %d attempts",
                max_retries,
                extra={"service": "database"},
            )
            # 연결 실패 시 생성한 엔진 리소스 정리
            await self.disconnect()
            return False

        return True

    async def health_check(self) -> bool:
        """데이터베이스 연결 상태를 확인합니다 (헬스체크용).

        ``SELECT 1`` 쿼리를 실행하여 데이터베이스가 응답 가능한지 확인합니다.

        Returns:
            연결이 정상이면 True, 엔진이 없거나 쿼리가 실패하면 False.
        """
        if self.engine is None:
            return False
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as exc:  # noqa: BLE001 - 헬스체크는 모든 오류를 비정상으로 처리
            logger.warning(
                "Database health check failed: %s",
                exc,
                extra={"service": "database", "error": str(exc)},
            )
            return False

    async def disconnect(self) -> None:
        """엔진을 종료하고 연결 풀의 모든 연결을 정리합니다."""
        if self.engine is not None:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None


# 애플리케이션 전역에서 공유하는 Database 인스턴스
database = Database()
