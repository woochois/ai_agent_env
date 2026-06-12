"""데이터베이스 Agent Tool 동작 테스트 (DB 모킹).

dbutil.fetch_all을 각 tool 모듈에서 패치하여 DB 없이 Tool 실행 경로를 검증합니다.
또한 DB 미가용 시 graceful 처리도 확인합니다.
"""

from __future__ import annotations

import pytest

from app.tool_agents.data_profiler_agent import tool as profiler_tool
from app.tool_agents.data_quality_agent import tool as quality_tool
from app.tool_agents.schema_inspector_agent import tool as schema_tool


def _fake_db():
    """resolve_engine이 non-None을 반환하도록 .engine을 가진 더미 객체."""
    class _DB:
        engine = object()

    return _DB()


# --- Schema Inspector ---


@pytest.mark.asyncio
async def test_schema_inspector_returns_structure(monkeypatch):
    async def fake_fetch_all(db, sql, params=None):
        if "information_schema.columns" in sql:
            return [{"column_name": "id", "data_type": "uuid", "is_nullable": "NO", "column_default": None}]
        if "pg_indexes" in sql:
            return [{"indexname": "pk_t", "indexdef": "CREATE UNIQUE INDEX ..."}]
        return [{"constraint_type": "PRIMARY KEY", "constraint_name": "pk_t", "column_name": "id"}]

    monkeypatch.setattr(schema_tool, "fetch_all", fake_fetch_all)
    factory_db = _fake_db()
    tool = schema_tool.SchemaInspectorTool(db_provider=lambda: factory_db)

    content, artifact = await tool._arun(table="t", schema_name="public")
    assert artifact["exists"] is True
    assert artifact["columns"][0]["column_name"] == "id"
    assert len(artifact["indexes"]) == 1
    assert len(artifact["constraints"]) == 1


@pytest.mark.asyncio
async def test_schema_inspector_no_db():
    tool = schema_tool.SchemaInspectorTool(db_provider=lambda: None)
    content, artifact = await tool._arun(table="t")
    assert artifact["note"] == "database_unavailable"


@pytest.mark.asyncio
async def test_schema_inspector_table_not_found(monkeypatch):
    async def fake_fetch_all(db, sql, params=None):
        return []  # 컬럼 없음 → 테이블 없음

    monkeypatch.setattr(schema_tool, "fetch_all", fake_fetch_all)
    tool = schema_tool.SchemaInspectorTool(db_provider=_fake_db)
    content, artifact = await tool._arun(table="missing")
    assert artifact["exists"] is False


# --- Data Profiler ---


@pytest.mark.asyncio
async def test_data_profiler_computes_rates(monkeypatch):
    async def fake_fetch_all(db, sql, params=None):
        if "information_schema.columns" in sql:
            return [{"column_name": "email"}, {"column_name": "age"}]
        # 집계 쿼리 결과
        return [{"row_count": 100, "email__non_null": 90, "email__distinct": 90,
                 "age__non_null": 100, "age__distinct": 40}]

    monkeypatch.setattr(profiler_tool, "fetch_all", fake_fetch_all)
    tool = profiler_tool.DataProfilerTool(db_provider=_fake_db)
    content, artifact = await tool._arun(table="users")

    assert artifact["row_count"] == 100
    email = next(c for c in artifact["columns"] if c["column"] == "email")
    assert email["null_count"] == 10
    assert email["null_rate"] == 0.1


@pytest.mark.asyncio
async def test_data_profiler_no_db():
    tool = profiler_tool.DataProfilerTool(db_provider=lambda: None)
    content, artifact = await tool._arun(table="t")
    assert artifact["note"] == "database_unavailable"


# --- Data Quality ---


@pytest.mark.asyncio
async def test_data_quality_runs_rules(monkeypatch):
    call_results = iter([
        [{"violations": 0}],   # not_null email
        [{"violations": 3}],   # range age
    ])

    async def fake_fetch_all(db, sql, params=None):
        return next(call_results)

    monkeypatch.setattr(quality_tool, "fetch_all", fake_fetch_all)
    tool = quality_tool.DataQualityTool(db_provider=_fake_db)
    content, artifact = await tool._arun(
        table="users",
        rules=[
            {"check": "not_null", "column": "email"},
            {"check": "range", "column": "age", "min": 0, "max": 120},
        ],
    )
    assert artifact["passed"] == 1
    assert artifact["failed"] == 1
    age_result = next(r for r in artifact["results"] if r["column"] == "age")
    assert age_result["violations"] == 3
    assert age_result["passed"] is False


@pytest.mark.asyncio
async def test_data_quality_no_db():
    tool = quality_tool.DataQualityTool(db_provider=lambda: None)
    content, artifact = await tool._arun(table="t", rules=[{"check": "not_null", "column": "x"}])
    assert artifact["note"] == "database_unavailable"
