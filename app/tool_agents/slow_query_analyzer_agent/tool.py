"""Slow Query Analyzer Agent Tool 구현.

``pg_stat_statements`` 확장을 조회하여 평균 실행 시간이 높은 쿼리 상위 N개를
반환합니다. 확장이 설치되지 않은 경우 안내 메시지를 반환합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact
from app.framework.dbutil import DBProvider, fetch_all, resolve_engine

AGENT_TYPE = "slow_query_analyzer_agent"

# pg_stat_statements 확장 설치 여부 확인
_EXT_CHECK_SQL = """
SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
"""

# PG13+ 컬럼명 (total_exec_time, mean_exec_time)
_TOP_SQL = """
SELECT query, calls, rows,
       round(total_exec_time::numeric, 2) AS total_exec_time_ms,
       round(mean_exec_time::numeric, 2) AS mean_exec_time_ms
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT :limit
"""


class SlowQueryInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=100, description="반환할 상위 쿼리 수")


class SlowQueryAnalyzerTool(BaseAgentTool):
    db_provider: DBProvider | None = Field(default=None, exclude=True)
    name: str = "analyze_slow_queries"
    description: str = (
        "pg_stat_statements를 분석하여 평균 실행 시간이 높은 쿼리 상위 N개를 반환합니다."
    )
    args_schema: type[BaseModel] = SlowQueryInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, limit: int = 10, config=None):
        raise NotImplementedError("비동기(_arun)로만 실행됩니다")

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="슬로우 쿼리 분석 중 오류가 발생했습니다", queries=[])
    async def _arun(self, limit: int = 10, config: RunnableConfig | None = None):
        db = self.db_provider() if self.db_provider else None
        if resolve_engine(db) is None:
            return "", build_artifact(AGENT_TYPE, note="database_unavailable", queries=[])

        ext = await fetch_all(db, _EXT_CHECK_SQL)
        if not ext:
            return "", build_artifact(
                AGENT_TYPE,
                note="extension_missing",
                hint="CREATE EXTENSION pg_stat_statements; 후 재시도하세요.",
                queries=[],
            )

        queries = await fetch_all(db, _TOP_SQL, {"limit": limit})
        return "", build_artifact(AGENT_TYPE, queries=queries, count=len(queries))

    def format_content(self, message: ToolMessage) -> ToolMessage:
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if art.get("note") == "database_unavailable":
            return message.model_copy(update={"content": "데이터베이스에 연결할 수 없습니다."})
        if art.get("note") == "extension_missing":
            return message.model_copy(
                update={"content": f"pg_stat_statements 확장이 없습니다. {art.get('hint')}"}
            )
        queries = art.get("queries", [])
        if not queries:
            return message.model_copy(update={"content": "수집된 쿼리 통계가 없습니다."})
        lines = ["평균 실행시간 상위 쿼리:"]
        for q in queries:
            snippet = (q.get("query", "") or "")[:80]
            lines.append(
                f"  - {q.get('mean_exec_time_ms')}ms (호출 {q.get('calls')}회): {snippet}"
            )
        return message.model_copy(update={"content": "\n".join(lines)})
