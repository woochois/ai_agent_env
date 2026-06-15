"""영속 상태 관리 모듈.

StateStore 인터페이스와 PostgreSQL/InMemory 구현을 제공합니다.
대화 세션 상태를 영속 저장하여 서버 재시작 후에도 대화를 이어갈 수 있습니다.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 8.11
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# session_id 검증 패턴: 알파벳, 숫자, 하이픈, 언더스코어만 허용, 최대 64자
SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def validate_session_id(session_id: str) -> None:
    """session_id 형식을 검증합니다.

    Args:
        session_id: 검증할 세션 ID 문자열.

    Raises:
        ValueError: 빈 문자열이거나 64자 초과이거나 허용되지 않는 문자 포함 시.
    """
    if not session_id:
        raise ValueError("session_id must be a non-empty string")
    if not SESSION_ID_PATTERN.match(session_id):
        raise ValueError(
            f"Invalid session_id '{session_id}': must be 1-64 characters, "
            "containing only alphanumeric characters, hyphens, and underscores"
        )


class StateStore(ABC):
    """세션 상태 영속 저장소 인터페이스.

    대화 상태를 저장/로드/삭제하고 세션 목록을 조회합니다.
    """

    @abstractmethod
    async def save_state(self, session_id: str, state: dict) -> None:
        """세션 상태를 저장합니다 (UPSERT).

        Args:
            session_id: 세션 식별자 (최대 64자, 영숫자/하이픈/언더스코어).
            state: 저장할 상태 딕셔너리.

        Raises:
            ValueError: 유효하지 않은 session_id.
        """
        ...

    @abstractmethod
    async def load_state(self, session_id: str) -> dict | None:
        """세션 상태를 로드합니다.

        Args:
            session_id: 세션 식별자.

        Returns:
            저장된 상태 딕셔너리, 없거나 만료된 경우 None.

        Raises:
            ValueError: 유효하지 않은 session_id.
        """
        ...

    @abstractmethod
    async def delete_state(self, session_id: str) -> None:
        """세션 상태를 삭제합니다.

        Args:
            session_id: 세션 식별자.

        Raises:
            ValueError: 유효하지 않은 session_id.
        """
        ...

    @abstractmethod
    async def list_sessions(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        """세션 목록을 조회합니다.

        Args:
            limit: 반환할 최대 세션 수 (1-100, 기본 50).
            offset: 건너뛸 세션 수 (0 이상, 기본 0).

        Returns:
            세션 메타데이터 딕셔너리 목록 (updated_at 내림차순).
        """
        ...

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """만료된 세션을 정리합니다.

        Returns:
            삭제된 세션 수.
        """
        ...


class InMemoryStateStore(StateStore):
    """인메모리 StateStore 구현 (테스트 및 폴백용).

    서버 재시작 시 모든 상태가 소실됩니다.
    """

    def __init__(self, ttl_hours: int = 24) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._ttl_hours = ttl_hours

    @property
    def ttl_hours(self) -> int:
        return self._ttl_hours

    async def save_state(self, session_id: str, state: dict) -> None:
        validate_session_id(session_id)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self._ttl_hours)

        if session_id in self._store:
            # UPSERT: update existing
            self._store[session_id]["state_json"] = state
            self._store[session_id]["updated_at"] = now
            self._store[session_id]["expires_at"] = expires_at
        else:
            # Insert new
            self._store[session_id] = {
                "session_id": session_id,
                "state_json": state,
                "created_at": now,
                "updated_at": now,
                "expires_at": expires_at,
            }

    async def load_state(self, session_id: str) -> dict | None:
        validate_session_id(session_id)
        entry = self._store.get(session_id)
        if entry is None:
            return None

        now = datetime.now(timezone.utc)
        if entry["expires_at"] <= now:
            # Expired - treat as not found
            return None

        return entry["state_json"]

    async def delete_state(self, session_id: str) -> None:
        validate_session_id(session_id)
        self._store.pop(session_id, None)

    async def list_sessions(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        # Clamp limit to 1-100
        limit = max(1, min(100, limit))
        offset = max(0, offset)

        now = datetime.now(timezone.utc)
        # Filter out expired sessions, sort by updated_at descending
        active_sessions = [
            entry
            for entry in self._store.values()
            if entry["expires_at"] > now
        ]
        active_sessions.sort(key=lambda x: x["updated_at"], reverse=True)

        # Apply pagination
        page = active_sessions[offset : offset + limit]
        return [
            {
                "session_id": entry["session_id"],
                "created_at": entry["created_at"].isoformat(),
                "updated_at": entry["updated_at"].isoformat(),
                "expires_at": entry["expires_at"].isoformat(),
            }
            for entry in page
        ]

    async def cleanup_expired(self) -> int:
        now = datetime.now(timezone.utc)
        expired_ids = [
            sid
            for sid, entry in self._store.items()
            if entry["expires_at"] <= now
        ]
        for sid in expired_ids:
            del self._store[sid]
        return len(expired_ids)


class PostgresStateStore(StateStore):
    """PostgreSQL 기반 StateStore 구현.

    sessions 테이블을 사용하여 대화 상태를 영속 저장합니다.
    asyncpg를 사용한 비동기 DB 접근을 제공합니다.
    """

    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id VARCHAR(64) PRIMARY KEY,
        state_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours'
    );
    """

    CREATE_INDEX_SQL = """
    CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at);
    """

    UPSERT_SQL = """
    INSERT INTO sessions (session_id, state_json, created_at, updated_at, expires_at)
    VALUES ($1, $2::jsonb, $3, $4, $5)
    ON CONFLICT (session_id)
    DO UPDATE SET
        state_json = EXCLUDED.state_json,
        updated_at = EXCLUDED.updated_at,
        expires_at = EXCLUDED.expires_at;
    """

    SELECT_SQL = """
    SELECT state_json FROM sessions
    WHERE session_id = $1 AND expires_at > NOW();
    """

    DELETE_SQL = """
    DELETE FROM sessions WHERE session_id = $1;
    """

    LIST_SQL = """
    SELECT session_id, created_at, updated_at, expires_at
    FROM sessions
    WHERE expires_at > NOW()
    ORDER BY updated_at DESC
    LIMIT $1 OFFSET $2;
    """

    CLEANUP_SQL = """
    DELETE FROM sessions WHERE expires_at <= NOW();
    """

    def __init__(self, database_url: str, ttl_hours: int = 24) -> None:
        self._database_url = database_url
        self._ttl_hours = ttl_hours
        self._pool = None

    @property
    def ttl_hours(self) -> int:
        return self._ttl_hours

    async def initialize(self) -> None:
        """DB 연결 풀을 생성하고 sessions 테이블을 초기화합니다."""
        import asyncpg
        import json

        self._pool = await asyncpg.create_pool(
            self._database_url,
            min_size=2,
            max_size=10,
            command_timeout=5,
        )
        async with self._pool.acquire() as conn:
            await conn.execute(self.CREATE_TABLE_SQL)
            await conn.execute(self.CREATE_INDEX_SQL)

    async def close(self) -> None:
        """연결 풀을 닫습니다."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def save_state(self, session_id: str, state: dict) -> None:
        import json

        validate_session_id(session_id)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self._ttl_hours)

        async with self._pool.acquire() as conn:
            await conn.execute(
                self.UPSERT_SQL,
                session_id,
                json.dumps(state, ensure_ascii=False, default=str),
                now,
                now,
                expires_at,
            )

    async def load_state(self, session_id: str) -> dict | None:
        import json

        validate_session_id(session_id)

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(self.SELECT_SQL, session_id)

        if row is None:
            return None

        state_json = row["state_json"]
        if isinstance(state_json, str):
            return json.loads(state_json)
        return state_json  # asyncpg auto-converts JSONB to dict

    async def delete_state(self, session_id: str) -> None:
        validate_session_id(session_id)

        async with self._pool.acquire() as conn:
            await conn.execute(self.DELETE_SQL, session_id)

    async def list_sessions(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        limit = max(1, min(100, limit))
        offset = max(0, offset)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(self.LIST_SQL, limit, offset)

        return [
            {
                "session_id": row["session_id"],
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
                "expires_at": row["expires_at"].isoformat(),
            }
            for row in rows
        ]

    async def cleanup_expired(self) -> int:
        async with self._pool.acquire() as conn:
            result = await conn.execute(self.CLEANUP_SQL)
            # asyncpg returns "DELETE N"
            count_str = result.split(" ")[-1]
            return int(count_str) if count_str.isdigit() else 0


def get_checkpointer():
    """LangGraph용 체크포인터를 반환합니다.

    PostgresSaver 사용을 시도하고, 실패 시 InMemorySaver로 폴백합니다.

    Returns:
        tuple: (checkpointer, persistence_type) where persistence_type is
               "postgresql" or "in_memory".
    """
    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        from app.config import get_settings

        settings = get_settings()
        checkpointer = PostgresSaver.from_conn_string(settings.DATABASE_URL)
        logger.info("Using PostgresSaver for state persistence")
        return checkpointer, "postgresql"
    except Exception as e:
        logger.warning(
            "Failed to initialize PostgresSaver, falling back to InMemorySaver: %s",
            str(e),
        )
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver(), "in_memory"


async def cleanup_expired_sessions(store: StateStore) -> int:
    """만료된 세션을 정리하는 백그라운드 태스크 함수.

    FastAPI의 BackgroundTasks 또는 주기적 스케줄러에서 호출하여 사용합니다.

    Args:
        store: StateStore 인스턴스.

    Returns:
        삭제된 세션 수.
    """
    try:
        count = await store.cleanup_expired()
        if count > 0:
            logger.info("Cleaned up %d expired sessions", count)
        return count
    except Exception as e:
        logger.warning("Failed to cleanup expired sessions: %s", str(e))
        return 0
