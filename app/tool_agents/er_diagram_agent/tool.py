"""ER Diagram Agent Tool 구현.

스키마의 테이블/컬럼과 외래키 관계를 조회하여 Mermaid erDiagram 텍스트를 생성합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact
from app.framework.dbutil import DBProvider, fetch_all, resolve_engine

AGENT_TYPE = "er_diagram_agent"

_COLUMNS_SQL = """
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = :schema
ORDER BY table_name, ordinal_position
"""

_FK_SQL = """
SELECT tc.table_name AS from_table,
       kcu.column_name AS from_column,
       ccu.table_name AS to_table,
       ccu.column_name AS to_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = :schema
"""


def _sanitize_type(data_type: str) -> str:
    """Mermaid 식별자에 안전하도록 타입명을 정규화합니다."""
    return data_type.replace(" ", "_").replace("(", "").replace(")", "")


def build_mermaid_erd(columns: list[dict], fks: list[dict]) -> str:
    """컬럼/FK 정보로부터 Mermaid erDiagram 문자열을 생성합니다."""
    tables: dict[str, list[tuple[str, str]]] = {}
    for row in columns:
        tables.setdefault(row["table_name"], []).append(
            (_sanitize_type(row["data_type"]), row["column_name"])
        )

    lines = ["erDiagram"]
    for table, cols in tables.items():
        lines.append(f"  {table} {{")
        for dtype, cname in cols:
            lines.append(f"    {dtype} {cname}")
        lines.append("  }")

    for fk in fks:
        # from_table 다수 → to_table 하나 (N:1)
        lines.append(
            f'  {fk["to_table"]} ||--o{{ {fk["from_table"]} : "{fk["from_column"]}"'
        )
    return "\n".join(lines)


class ERDiagramInput(BaseModel):
    schema_name: str = Field(default="public", description="대상 스키마명")


class ERDiagramTool(BaseAgentTool):
    db_provider: DBProvider | None = Field(default=None, exclude=True)
    name: str = "generate_erd"
    description: str = (
        "스키마의 테이블/컬럼과 외래키 관계로부터 Mermaid ER 다이어그램을 생성합니다."
    )
    args_schema: type[BaseModel] = ERDiagramInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, schema_name: str = "public", config=None):
        raise NotImplementedError("비동기(_arun)로만 실행됩니다")

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="ER 다이어그램 생성 중 오류가 발생했습니다")
    async def _arun(self, schema_name: str = "public", config: RunnableConfig | None = None):
        db = self.db_provider() if self.db_provider else None
        if resolve_engine(db) is None:
            return "", build_artifact(AGENT_TYPE, note="database_unavailable")

        columns = await fetch_all(db, _COLUMNS_SQL, {"schema": schema_name})
        fks = await fetch_all(db, _FK_SQL, {"schema": schema_name})
        mermaid = build_mermaid_erd(columns, fks)
        table_count = len({c["table_name"] for c in columns})
        return "", build_artifact(
            AGENT_TYPE, schema=schema_name, mermaid=mermaid,
            table_count=table_count, fk_count=len(fks),
        )

    def format_content(self, message: ToolMessage) -> ToolMessage:
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if art.get("note") == "database_unavailable":
            return message.model_copy(update={"content": "데이터베이스에 연결할 수 없습니다."})
        mermaid = art.get("mermaid", "")
        return message.model_copy(update={"content": f"```mermaid\n{mermaid}\n```"})
