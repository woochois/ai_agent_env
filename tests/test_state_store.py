"""State Store 단위 및 Property-Based 테스트.

InMemoryStateStore를 사용하여 StateStore 인터페이스의 정확성을 검증합니다.

Feature: agent-consolidation-advanced
Properties: 15, 16, 17
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.framework.state_store import (
    InMemoryStateStore,
    StateStore,
    cleanup_expired_sessions,
    get_checkpointer,
    validate_session_id,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid session_id: 1-64 chars, alphanumeric + hyphens + underscores
valid_session_id_chars = st.sampled_from(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)
valid_session_ids = st.text(valid_session_id_chars, min_size=1, max_size=64)

# Invalid session_ids: empty, too long, or containing invalid chars
invalid_session_ids = st.one_of(
    st.just(""),  # empty
    st.text(valid_session_id_chars, min_size=65, max_size=100),  # too long
    st.text(
        st.characters(
            min_codepoint=32, max_codepoint=126,
            blacklist_characters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        ),
        min_size=1,
        max_size=64,
    ),  # invalid characters
)

# Serializable state dicts for testing
simple_values = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1000, max_value=1000),
    st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
    st.text(min_size=0, max_size=50),
)
state_dicts = st.dictionaries(
    keys=st.text(min_size=1, max_size=20),
    values=simple_values,
    min_size=0,
    max_size=10,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store():
    """테스트용 InMemoryStateStore 인스턴스."""
    return InMemoryStateStore(ttl_hours=24)


@pytest.fixture
def short_ttl_store():
    """짧은 TTL의 InMemoryStateStore (만료 테스트용)."""
    return InMemoryStateStore(ttl_hours=0)  # 즉시 만료


# ---------------------------------------------------------------------------
# Property 15: State_Store 영속성 라운드트립
# Feature: agent-consolidation-advanced, Property 15: State_Store 영속성 라운드트립
# ---------------------------------------------------------------------------


class TestStateStoreRoundTrip:
    """**Validates: Requirements 8.4, 8.8, 8.10**"""

    @settings(max_examples=100)
    @given(session_id=valid_session_ids, state=state_dicts)
    def test_save_load_roundtrip(self, session_id, state):
        """save_state 후 load_state하면 동일한 상태가 반환되어야 한다."""
        store = InMemoryStateStore(ttl_hours=24)

        async def _run():
            await store.save_state(session_id, state)
            loaded = await store.load_state(session_id)
            assert loaded == state, (
                f"Round-trip failed: saved {state}, loaded {loaded}"
            )

        asyncio.get_event_loop().run_until_complete(_run())

    @settings(max_examples=100)
    @given(
        session_id=valid_session_ids,
        state1=state_dicts,
        state2=state_dicts,
    )
    def test_upsert_overwrites(self, session_id, state1, state2):
        """동일 session_id로 두 번 save_state하면 마지막 상태만 유지 (UPSERT)."""
        store = InMemoryStateStore(ttl_hours=24)

        async def _run():
            await store.save_state(session_id, state1)
            await store.save_state(session_id, state2)
            loaded = await store.load_state(session_id)
            assert loaded == state2, (
                f"UPSERT failed: expected {state2}, got {loaded}"
            )

        asyncio.get_event_loop().run_until_complete(_run())


# ---------------------------------------------------------------------------
# Property 16: State_Store session_id 검증
# Feature: agent-consolidation-advanced, Property 16: State_Store session_id 검증
# ---------------------------------------------------------------------------


class TestSessionIdValidation:
    """**Validates: Requirements 8.11**"""

    @settings(max_examples=100)
    @given(session_id=invalid_session_ids)
    def test_invalid_session_id_raises_value_error(self, session_id):
        """유효하지 않은 session_id는 ValueError를 발생시켜야 한다."""
        store = InMemoryStateStore(ttl_hours=24)

        async def _run():
            with pytest.raises(ValueError):
                await store.save_state(session_id, {"test": "data"})

        asyncio.get_event_loop().run_until_complete(_run())

    @settings(max_examples=100)
    @given(session_id=invalid_session_ids)
    def test_invalid_session_id_load_raises(self, session_id):
        """load_state에서도 유효하지 않은 session_id는 ValueError."""
        store = InMemoryStateStore(ttl_hours=24)

        async def _run():
            with pytest.raises(ValueError):
                await store.load_state(session_id)

        asyncio.get_event_loop().run_until_complete(_run())

    @settings(max_examples=100)
    @given(session_id=invalid_session_ids)
    def test_invalid_session_id_delete_raises(self, session_id):
        """delete_state에서도 유효하지 않은 session_id는 ValueError."""
        store = InMemoryStateStore(ttl_hours=24)

        async def _run():
            with pytest.raises(ValueError):
                await store.delete_state(session_id)

        asyncio.get_event_loop().run_until_complete(_run())

    @settings(max_examples=100)
    @given(session_id=valid_session_ids)
    def test_valid_session_id_accepted(self, session_id):
        """유효한 session_id는 예외 없이 처리되어야 한다."""
        store = InMemoryStateStore(ttl_hours=24)

        async def _run():
            await store.save_state(session_id, {"key": "value"})
            result = await store.load_state(session_id)
            assert result == {"key": "value"}

        asyncio.get_event_loop().run_until_complete(_run())


# ---------------------------------------------------------------------------
# Property 17: State_Store TTL 및 페이지네이션
# Feature: agent-consolidation-advanced, Property 17: State_Store TTL 및 페이지네이션
# ---------------------------------------------------------------------------


class TestTTLAndPagination:
    """**Validates: Requirements 8.7, 8.9**"""

    @settings(max_examples=50)
    @given(
        session_ids=st.lists(valid_session_ids, min_size=1, max_size=20, unique=True),
        limit=st.integers(min_value=1, max_value=100),
        offset=st.integers(min_value=0, max_value=50),
    )
    def test_list_sessions_pagination(self, session_ids, limit, offset):
        """list_sessions는 limit/offset에 따라 올바른 페이지를 반환해야 한다."""
        store = InMemoryStateStore(ttl_hours=24)

        async def _run():
            # Save multiple sessions
            for sid in session_ids:
                await store.save_state(sid, {"id": sid})

            result = await store.list_sessions(limit=limit, offset=offset)

            # Result count should be <= limit
            assert len(result) <= limit
            # Result count should be <= total - offset (or 0 if offset > total)
            expected_max = max(0, len(session_ids) - offset)
            assert len(result) <= expected_max

        asyncio.get_event_loop().run_until_complete(_run())

    @settings(max_examples=50)
    @given(
        session_ids=st.lists(valid_session_ids, min_size=2, max_size=10, unique=True),
    )
    def test_list_sessions_ordered_by_updated_at_desc(self, session_ids):
        """list_sessions는 updated_at 내림차순으로 정렬해야 한다."""
        store = InMemoryStateStore(ttl_hours=24)

        async def _run():
            for sid in session_ids:
                await store.save_state(sid, {"id": sid})

            result = await store.list_sessions(limit=100, offset=0)

            # Check descending order by updated_at
            for i in range(len(result) - 1):
                assert result[i]["updated_at"] >= result[i + 1]["updated_at"]

        asyncio.get_event_loop().run_until_complete(_run())

    def test_expired_sessions_not_returned_by_load(self):
        """만료된 세션은 load_state에서 None을 반환해야 한다."""
        store = InMemoryStateStore(ttl_hours=0)

        async def _run():
            await store.save_state("test-session", {"data": "value"})
            # With ttl_hours=0, the session expires immediately
            # (expires_at = now + 0 hours = now, and condition is expires_at <= now)
            result = await store.load_state("test-session")
            assert result is None

        asyncio.get_event_loop().run_until_complete(_run())

    def test_expired_sessions_not_in_list(self):
        """만료된 세션은 list_sessions에 포함되지 않아야 한다."""
        store = InMemoryStateStore(ttl_hours=0)

        async def _run():
            await store.save_state("expired-session", {"data": "old"})
            result = await store.list_sessions()
            session_ids = [s["session_id"] for s in result]
            assert "expired-session" not in session_ids

        asyncio.get_event_loop().run_until_complete(_run())

    def test_cleanup_removes_expired(self):
        """cleanup_expired는 만료된 세션을 제거해야 한다."""
        store = InMemoryStateStore(ttl_hours=0)

        async def _run():
            await store.save_state("to-clean", {"data": "value"})
            count = await store.cleanup_expired()
            assert count >= 1
            # Verify the session is gone from internal store
            assert "to-clean" not in store._store

        asyncio.get_event_loop().run_until_complete(_run())


# ---------------------------------------------------------------------------
# Unit Tests: Additional edge cases
# ---------------------------------------------------------------------------


class TestStateStoreEdgeCases:
    """추가 단위 테스트: 미존재 세션, 삭제, 폴백 등."""

    @pytest.mark.asyncio
    async def test_load_nonexistent_returns_none(self, store):
        """존재하지 않는 세션은 None을 반환해야 한다."""
        result = await store.load_state("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing_session(self, store):
        """삭제 후 load_state는 None을 반환해야 한다."""
        await store.save_state("to-delete", {"hello": "world"})
        await store.delete_state("to-delete")
        result = await store.load_state("to-delete")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_no_error(self, store):
        """존재하지 않는 세션 삭제 시 에러가 발생하지 않아야 한다."""
        await store.delete_state("does-not-exist")  # Should not raise

    @pytest.mark.asyncio
    async def test_list_sessions_default_params(self, store):
        """기본 매개변수로 빈 목록을 반환해야 한다."""
        result = await store.list_sessions()
        assert result == []

    @pytest.mark.asyncio
    async def test_ttl_configuration(self):
        """TTL 설정이 올바르게 적용되어야 한다."""
        store = InMemoryStateStore(ttl_hours=48)
        assert store.ttl_hours == 48


class TestGetCheckpointer:
    """get_checkpointer() 폴백 동작 테스트."""

    def test_fallback_to_in_memory(self):
        """PostgresSaver 불가 시 InMemorySaver로 폴백해야 한다."""
        checkpointer, persistence_type = get_checkpointer()
        # In test environment without langgraph-checkpoint-postgres,
        # it should fall back to InMemorySaver
        from langgraph.checkpoint.memory import InMemorySaver

        assert isinstance(checkpointer, InMemorySaver)
        assert persistence_type == "in_memory"


class TestCleanupExpiredSessions:
    """cleanup_expired_sessions 유틸리티 함수 테스트."""

    @pytest.mark.asyncio
    async def test_cleanup_function(self):
        """cleanup_expired_sessions 함수가 올바르게 작동해야 한다."""
        store = InMemoryStateStore(ttl_hours=0)
        await store.save_state("sess-1", {"a": 1})
        await store.save_state("sess-2", {"b": 2})

        count = await cleanup_expired_sessions(store)
        assert count >= 2

    @pytest.mark.asyncio
    async def test_cleanup_no_expired(self):
        """만료된 세션이 없으면 0을 반환해야 한다."""
        store = InMemoryStateStore(ttl_hours=24)
        await store.save_state("active-sess", {"data": "value"})

        count = await cleanup_expired_sessions(store)
        assert count == 0


class TestValidateSessionId:
    """validate_session_id 함수 직접 테스트."""

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            validate_session_id("")

    def test_too_long_raises(self):
        with pytest.raises(ValueError, match="1-64 characters"):
            validate_session_id("a" * 65)

    def test_special_chars_raises(self):
        with pytest.raises(ValueError):
            validate_session_id("session@id!")

    def test_spaces_raises(self):
        with pytest.raises(ValueError):
            validate_session_id("session id")

    def test_valid_alphanumeric(self):
        validate_session_id("abc123")  # Should not raise

    def test_valid_with_hyphens(self):
        validate_session_id("my-session-id")  # Should not raise

    def test_valid_with_underscores(self):
        validate_session_id("my_session_id")  # Should not raise

    def test_max_length_valid(self):
        validate_session_id("a" * 64)  # Should not raise
