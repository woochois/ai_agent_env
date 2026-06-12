"""Data Profiler Agent Tool 구현.

테이블의 행 수, 컬럼별 NULL 비율/고유값 수를 집계합니다. 컬럼명은
information_schema에서 조회한 뒤 안전하게 따옴표 처리하여 집계 쿼리를 구성합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact
from app.framework.dbutil import (
    DBProvider,
    fetch_all,
    qualified_table,
    quote_ident,
    resolve_engine,
)

AGENT_TYPE = "data_profiler_agent"

_COLS_SQL = """
SELECT column_name
FROM information_schema.columns
WHERE table_schema = :schema AND table_name = :table
ORDER BY ordinal_position
LIMIT :max_cols
"""


class DataProfilerInput(BaseModel):
    table: str = Field(..., description="프로파일링할 테이블명")
    schema_name: str = Field(default="public", description="스키마명")
    max_columns: int = Field(default=30, ge=1, le=100, description="프로파일링할 최대 컬럼 수")


class DataProfilerTool(BaseAgentTool):
    db_provider: DBProvider | None = Field(default=None, exclude=True)
    name: str = "profile_data"
    description: str = (
        "테이블의 행 수와 컬럼별 NULL 비율, 고유값 수를 집계하여 데이터 품질 개요를 제공합니다."
    )
    args_schema: type[BaseModel] = DataProfilerInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, table: str, schema_name: str = "public", max_columns: int = 30, config=None):
        raise NotImplementedError("비동기(_arun)로만 실행됩니다")

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="데이터 프로파일링 중 오류가 발생했습니다", columns=[])
    async def _arun(
        self,
        table: str,
        schema_name: str = "public",
        max_columns: int = 30,
        config: RunnableConfig | None = None,
    ):
        db = self.db_provider() if self.db_provider else None
        if resolve_engine(db) is None:
            return "", build_artifact(AGENT_TYPE, note="database_unavailable", columns=[])

        col_rows = await fetch_all(
            db, _COLS_SQL, {"schema": schema_name, "table": table, "max_cols": max_columns}
        )
        if not col_rows:
            return "", build_artifact(AGENT_TYPE, table=table, exists=False, columns=[])

        col_names = [r["column_name"] for r in col_rows]
        fq = qualified_table(table, schema_name)

        # 집계 쿼리 구성 (식별자 안전 처리)
        select_parts = ["COUNT(*) AS row_count"]
        for col in col_names:
            qc = quote_ident(col)
            alias = col.replace('"', "")
            select_parts.append(f"COUNT({qc}) AS \"{alias}__non_null\"")
            select_parts.append(f"COUNT(DISTINCT {qc}) AS \"{alias}__distinct\"")
        agg_sql = f"SELECT {', '.join(select_parts)} FROM {fq}"

        rows = await fetch_all(db, agg_sql)
        agg = rows[0] if rows else {}
        total = int(agg.get("row_count", 0) or 0)

        profiles = []
        for col in col_names:
            non_null = int(agg.get(f"{col}__non_null", 0) or 0)
            distinct = int(agg.get(f"{col}__distinct", 0) or 0)
            null_count = total - non_null
            profiles.append(
                {
                    "column": col,
                    "non_null": non_null,
                    "null_count": null_count,
                    "null_rate": round(null_count / total, 4) if total else 0.0,
                    "distinct": distinct,
                    "distinct_rate": round(distinct / total, 4) if total else 0.0,
                }
            )

        return "", build_artifact(
            AGENT_TYPE, table=table, schema=schema_name, exists=True,
            row_count=total, columns=profiles,
        )

    def format_content(self, message: ToolMessage) -> ToolMessage:
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if art.get("note") == "database_unavailable":
            return message.model_copy(update={"content": "데이터베이스에 연결할 수 없습니다."})
        if not art.get("exists"):
            return message.model_copy(update={"content": "테이블을 찾을 수 없거나 컬럼이 없습니다."})
        lines = [f"테이블 {art.get('table')}: {art.get('row_count')}행"]
        for p in art.get("columns", []):
            lines.append(
                f"  - {p['column']}: NULL {p['null_rate']*100:.1f}%, 고유값 {p['distinct']}개"
            )
        return message.model_copy(update={"content": "\n".join(lines)})
