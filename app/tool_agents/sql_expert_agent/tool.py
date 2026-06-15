"""SQL Expert Agent Tool 구현.

기존 sql_formatter, sql_lint, query_explain, slow_query_analyzer 에이전트를
단일 Expert Agent로 통합합니다. sub_command 파라미터를 통해 내부 라우팅합니다.

Sub_Commands:
- format: SQL 키워드 대문자화 + 절 줄바꿈
- lint: SQL 안티패턴/위험 패턴 검출
- explain: EXPLAIN (FORMAT JSON) 실행계획 분석
- analyze_slow_query: pg_stat_statements 기반 느린 쿼리 분석
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from app.framework.base import (
    BaseAgentTool,
    auto_error_artifact,
    build_artifact,
    build_error_artifact,
)
from app.framework.dbutil import DBProvider, fetch_all, resolve_engine

AGENT_TYPE = "sql_expert"

_VALID_COMMANDS = frozenset({"format", "lint", "explain", "analyze_slow_query"})


class SqlExpertInput(BaseModel):
    """SQL Expert Agent 입력 스키마."""

    sub_command: str = Field(
        ..., description="실행할 서브커맨드: format | lint | explain | analyze_slow_query"
    )
    sql: str = Field(default="", description="SQL 쿼리 (format, lint용)")
    query: str = Field(default="", description="SQL 쿼리 (explain, analyze_slow_query용)")
    analyze: bool = Field(default=False, description="EXPLAIN ANALYZE 여부 (explain용)")
    limit: int = Field(default=10, ge=1, le=100, description="반환할 상위 쿼리 수 (analyze_slow_query용)")


class SqlExpertTool(BaseAgentTool):
    """통합 SQL Expert Agent Tool.

    sub_command에 따라 적절한 내부 핸들러로 라우팅합니다.
    """

    db_provider: DBProvider | None = Field(default=None, exclude=True)
    name: str = "sql_expert"
    description: str = (
        "SQL 관련 작업을 수행합니다. format(포맷팅), lint(안티패턴 검출), "
        "explain(실행계획 분석), analyze_slow_query(느린 쿼리 분석)를 지원합니다."
    )
    args_schema: type[BaseModel] = SqlExpertInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(
        self,
        sub_command: str,
        sql: str = "",
        query: str = "",
        analyze: bool = False,
        limit: int = 10,
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("비동기(_arun)로만 실행됩니다")

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="SQL Expert 실행 중 오류가 발생했습니다")
    async def _arun(
        self,
        sub_command: str,
        sql: str = "",
        query: str = "",
        analyze: bool = False,
        limit: int = 10,
        config: RunnableConfig | None = None,
    ) -> tuple[str, dict]:
        # Sub_command 검증
        if sub_command not in _VALID_COMMANDS:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message=f"Unknown sub_command: '{sub_command}'",
                error_detail=f"Valid sub_commands: {sorted(_VALID_COMMANDS)}",
                sub_command=sub_command,
                valid_commands=sorted(_VALID_COMMANDS),
            )

        # 핸들러 디스패치
        handler = getattr(self, f"_handle_{sub_command}")
        return await handler(sql=sql, query=query, analyze=analyze, limit=limit)

    async def _handle_format(self, sql: str, **kwargs: Any) -> tuple[str, dict]:
        """format 서브커맨드: SQL 키워드 대문자화 + 절 줄바꿈."""
        if not sql or not sql.strip():
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message="필수 입력 필드 'sql'이 비어 있습니다.",
                error_detail="format 서브커맨드는 sql 필드가 필요합니다.",
                sub_command="format",
                missing_field="sql",
            )

        from app.tool_agents.sql_formatter_agent.tool import format_sql

        formatted = format_sql(sql)
        return formatted, build_artifact(AGENT_TYPE, formatted_sql=formatted, original=sql)

    async def _handle_lint(self, sql: str, **kwargs: Any) -> tuple[str, dict]:
        """lint 서브커맨드: SQL 안티패턴/위험 패턴 검출."""
        if not sql or not sql.strip():
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message="필수 입력 필드 'sql'이 비어 있습니다.",
                error_detail="lint 서브커맨드는 sql 필드가 필요합니다.",
                sub_command="lint",
                missing_field="sql",
            )

        from app.tool_agents.sql_lint_agent.tool import lint_sql

        issues = lint_sql(sql)
        return "", build_artifact(AGENT_TYPE, issues=issues, sub_command="lint")

    async def _handle_explain(
        self, query: str, analyze: bool = False, **kwargs: Any
    ) -> tuple[str, dict]:
        """explain 서브커맨드: EXPLAIN (FORMAT JSON) 실행계획 분석."""
        if not query or not query.strip():
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message="필수 입력 필드 'query'이 비어 있습니다.",
                error_detail="explain 서브커맨드는 query 필드가 필요합니다.",
                sub_command="explain",
                missing_field="query",
            )

        # ANALYZE는 SELECT 쿼리에만 허용
        if analyze and not query.lstrip().upper().startswith("SELECT"):
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message="ANALYZE는 SELECT 쿼리에만 허용됩니다",
                error_detail="비-SELECT 쿼리에 대해 ANALYZE를 실행하면 부작용이 발생할 수 있습니다.",
                sub_command="explain",
            )

        # DB 연결 확인
        db = self.db_provider() if self.db_provider else None
        if resolve_engine(db) is None:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message="데이터베이스에 연결할 수 없습니다.",
                note="database_unavailable",
                sub_command="explain",
            )

        # EXPLAIN 실행
        from app.tool_agents.query_explain_agent.tool import analyze_plan

        options = "ANALYZE, FORMAT JSON" if analyze else "FORMAT JSON"
        explain_sql = f"EXPLAIN ({options}) {query}"
        rows = await fetch_all(db, explain_sql)

        # 결과 파싱
        from app.tool_agents.query_explain_agent.tool import _extract_plan

        plan_json = _extract_plan(rows)
        analysis = analyze_plan(plan_json)
        return "", build_artifact(AGENT_TYPE, analyzed=analyze, sub_command="explain", **analysis)

    async def _handle_analyze_slow_query(
        self, limit: int = 10, **kwargs: Any
    ) -> tuple[str, dict]:
        """analyze_slow_query 서브커맨드: pg_stat_statements 기반 느린 쿼리 분석."""
        # DB 연결 확인
        db = self.db_provider() if self.db_provider else None
        if resolve_engine(db) is None:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message="데이터베이스에 연결할 수 없습니다.",
                note="database_unavailable",
                sub_command="analyze_slow_query",
            )

        # pg_stat_statements 확장 확인
        ext_check_sql = (
            "SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'"
        )
        ext = await fetch_all(db, ext_check_sql)
        if not ext:
            return "", build_artifact(
                AGENT_TYPE,
                note="extension_missing",
                hint="CREATE EXTENSION pg_stat_statements; 후 재시도하세요.",
                queries=[],
                sub_command="analyze_slow_query",
            )

        # 쿼리 실행
        top_sql = """
            SELECT query, calls, rows,
                   round(total_exec_time::numeric, 2) AS total_exec_time_ms,
                   round(mean_exec_time::numeric, 2) AS mean_exec_time_ms
            FROM pg_stat_statements
            ORDER BY mean_exec_time DESC
            LIMIT :limit
        """
        queries = await fetch_all(db, top_sql, {"limit": limit})
        return "", build_artifact(
            AGENT_TYPE, queries=queries, count=len(queries), sub_command="analyze_slow_query"
        )
