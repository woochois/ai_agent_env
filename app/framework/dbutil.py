"""데이터베이스 Tool Agent용 공용 유틸리티.

PostgreSQL 백엔드를 사용하는 Tool Agent들이 읽기 전용 쿼리를 안전하게 실행하도록
돕습니다. DB 연결은 provider 콜러블로 주입되며, 기본 provider는 전역
``Database`` 인스턴스(app.main.get_db)를 지연 조회합니다.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)

#: Database 래퍼(.engine 보유) 또는 None을 반환하는 provider 타입.
DBProvider = Callable[[], Any]


def default_db_provider() -> Any | None:
    """전역 Database 인스턴스를 지연 조회하는 기본 provider."""
    try:
        from app.main import get_db

        return get_db()
    except Exception:  # noqa: BLE001 - 앱 컨텍스트 밖에서는 None
        return None


def resolve_engine(db: Any | None) -> Any | None:
    """Database 래퍼 또는 raw 엔진에서 AsyncEngine을 해석합니다."""
    if db is None:
        return None
    return getattr(db, "engine", db)


async def fetch_all(
    db: Any | None, sql: str, params: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """SELECT 쿼리를 실행하여 결과를 dict 리스트로 반환합니다.

    Args:
        db: Database 래퍼(.engine 보유) 또는 raw AsyncEngine.
        sql: 실행할 SQL (읽기 전용 권장).
        params: 바인드 파라미터.

    Returns:
        행(dict) 리스트.

    Raises:
        RuntimeError: DB 엔진을 사용할 수 없는 경우.
    """
    engine = resolve_engine(db)
    if engine is None:
        raise RuntimeError("database_unavailable")
    async with engine.connect() as conn:
        result = await conn.execute(text(sql), params or {})
        return [dict(row) for row in result.mappings().all()]


def quote_ident(identifier: str) -> str:
    """SQL 식별자(테이블/컬럼명)를 안전하게 큰따옴표로 감쌉니다.

    내부 큰따옴표는 이스케이프합니다. 식별자에 NUL 문자가 있으면 거부합니다.

    Args:
        identifier: 테이블/컬럼/스키마 식별자.

    Returns:
        따옴표로 감싼 안전한 식별자.

    Raises:
        ValueError: 식별자가 비었거나 NUL 문자를 포함한 경우.
    """
    if not identifier or "\x00" in identifier:
        raise ValueError(f"유효하지 않은 식별자입니다: {identifier!r}")
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def qualified_table(table: str, schema: str = "public") -> str:
    """스키마.테이블 형태의 안전한 정규화 식별자를 반환합니다."""
    return f"{quote_ident(schema)}.{quote_ident(table)}"
