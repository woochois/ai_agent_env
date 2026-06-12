"""DDL Generator Agent Tool 구현.

구조화된 컬럼 명세로부터 PostgreSQL CREATE TABLE DDL과 인덱스 DDL을 생성합니다.
실제 DB에 실행하지 않고 SQL 텍스트만 반환합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact

AGENT_TYPE = "ddl_generator_agent"


class ColumnSpec(BaseModel):
    name: str = Field(..., description="컬럼명")
    type: str = Field(..., description="데이터 타입 (예: VARCHAR(255), INTEGER, TIMESTAMPTZ)")
    nullable: bool = Field(default=True, description="NULL 허용 여부")
    primary_key: bool = Field(default=False, description="기본키 여부")
    unique: bool = Field(default=False, description="UNIQUE 제약 여부")
    default: str | None = Field(default=None, description="기본값 표현식 (예: NOW())")


class DDLGenInput(BaseModel):
    table_name: str = Field(..., description="생성할 테이블명")
    columns: list[ColumnSpec] = Field(..., description="컬럼 명세 목록")
    schema_name: str = Field(default="public", description="스키마명")
    if_not_exists: bool = Field(default=True, description="IF NOT EXISTS 포함 여부")


def generate_ddl(spec: DDLGenInput) -> dict:
    """명세로부터 CREATE TABLE DDL과 보조 인덱스 DDL을 생성합니다."""
    fq = f'"{spec.schema_name}"."{spec.table_name}"'
    exists = "IF NOT EXISTS " if spec.if_not_exists else ""

    col_lines: list[str] = []
    pk_cols: list[str] = []
    index_ddls: list[str] = []

    for col in spec.columns:
        parts = [f'"{col.name}"', col.type]
        if not col.nullable or col.primary_key:
            parts.append("NOT NULL")
        if col.default is not None:
            parts.append(f"DEFAULT {col.default}")
        col_lines.append("  " + " ".join(parts))
        if col.primary_key:
            pk_cols.append(f'"{col.name}"')
        if col.unique and not col.primary_key:
            idx = f'idx_{spec.table_name}_{col.name}_uniq'
            index_ddls.append(
                f'CREATE UNIQUE INDEX IF NOT EXISTS "{idx}" ON {fq} ("{col.name}");'
            )

    if pk_cols:
        col_lines.append(f"  PRIMARY KEY ({', '.join(pk_cols)})")

    create_ddl = f"CREATE TABLE {exists}{fq} (\n" + ",\n".join(col_lines) + "\n);"
    return {
        "create_table": create_ddl,
        "indexes": index_ddls,
        "full_ddl": "\n".join([create_ddl, *index_ddls]),
    }


class DDLGeneratorTool(BaseAgentTool):
    name: str = "generate_ddl"
    description: str = (
        "컬럼 명세(이름/타입/NULL/PK/UNIQUE/기본값)로부터 PostgreSQL CREATE TABLE "
        "DDL과 인덱스 DDL을 생성합니다."
    )
    args_schema: type[BaseModel] = DDLGenInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(self, config: RunnableConfig | None = None, **kwargs):
        return self._generate(DDLGenInput(**kwargs))

    async def _arun(self, config: RunnableConfig | None = None, **kwargs):
        return self._generate(DDLGenInput(**kwargs))

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="DDL 생성 중 오류가 발생했습니다")
    def _generate(self, spec: DDLGenInput) -> tuple[str, dict]:
        result = generate_ddl(spec)
        return result["full_ddl"], build_artifact(AGENT_TYPE, **result)

    def format_content(self, message: ToolMessage) -> ToolMessage:
        if isinstance(message.artifact, dict) and "full_ddl" in message.artifact:
            ddl = message.artifact["full_ddl"]
            return message.model_copy(update={"content": f"```sql\n{ddl}\n```"})
        return message
