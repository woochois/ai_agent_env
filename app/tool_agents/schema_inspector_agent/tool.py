"""Schema Inspector Agent Tool 구현.

information_schema / pg_catalog를 조회하여 테이블의 컬럼, 인덱스, 제약조건을
반환합니다. 모두 읽기 전용 쿼리이며 바인드 파라미터를 사용합니다.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact
from app.framework.dbutil import DBProvider, fetch_all, resolve_engine

AGENT_TYPE = "schema_inspector_agent"

_COLUMNS_SQL = """
SELECT column_name, data_type, is_nullable, column_default,
       character_maximum_length, numeric_precision, numeric_scale
FROM information_schema.columns
WHERE table_schema = :schema AND table_name = :table
ORDER BY ordinal_position
"""

_INDEXES_SQL = """
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = :schema AND tablename = :table
ORDER BY indexname
"""

_CONSTRAINTS_SQL = """
SELECT tc.constraint_type, tc.constraint_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
WHERE tc.table_schema = :schema AND tc.table_name = :table
ORDER BY tc.constraint_type, kcu.column_name
"""


class SchemaInspectInput(BaseModel):
    table: str = Field(..., description="조회할 테이블명")
    schema_name: str = Field(default="public", description="스키마명")


class SchemaInspectorTool(BaseAgentTool):
    db_provider: DBProvider | None = Field(default=None, exclude=True)
    name: str = "inspect_schema"
    description: str = (
        "테이블의 컬럼(타입/NULL/기본값), 인덱스, 제약조건(PK/FK/UNIQUE)을 조회합니다."
    )
    args_schema: type[BaseModel] = SchemaInspectInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, table: str, schema_name: str = "public", config=None):
        raise NotImplementedError("비동기(_arun)로만 실행됩니다")

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="스키마 조회 중 오류가 발생했습니다")
    async def _arun(self, table: str, schema_name: str = "public", config: RunnableConfig | None = None):
        db = self.db_provider() if self.db_provider else None
        if resolve_engine(db) is None:
            return "", build_artifact(AGENT_TYPE, note="database_unavailable", columns=[])

        params = {"schema": schema_name, "table": table}
        columns = await fetch_all(db, _COLUMNS_SQL, params)
        indexes = await fetch_all(db, _INDEXES_SQL, params)
        constraints = await fetch_all(db, _CONSTRAINTS_SQL, params)

        return "", build_artifact(
            AGENT_TYPE,
            table=table,
            schema=schema_name,
            exists=bool(columns),
            columns=columns,
            indexes=indexes,
            constraints=constraints,
        )

    def format_content(self, message: ToolMessage) -> ToolMessage:
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if art.get("note") == "database_unavailable":
            return message.model_copy(update={"content": "데이터베이스에 연결할 수 없습니다."})
        if not art.get("exists"):
            return message.model_copy(
                update={"content": f"테이블 '{art.get('table')}'을(를) 찾을 수 없습니다."}
            )
        lines = [f"테이블: {art.get('schema')}.{art.get('table')}", "컬럼:"]
        for col in art.get("columns", []):
            null = "NULL" if col.get("is_nullable") == "YES" else "NOT NULL"
            lines.append(f"  - {col['column_name']} {col['data_type']} {null}")
        lines.append(f"인덱스: {len(art.get('indexes', []))}개, 제약: {len(art.get('constraints', []))}개")
        return message.model_copy(update={"content": "\n".join(lines)})
