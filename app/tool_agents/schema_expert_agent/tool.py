"""Schema Expert Agent Tool 구현.

기존 ddl_generator, schema_inspector, er_diagram, index_advisor 에이전트를
단일 Expert Agent로 통합합니다. sub_command 파라미터를 통해 내부 라우팅합니다.

Sub_Commands:
- generate_ddl: 컬럼 명세로부터 CREATE TABLE DDL 생성
- inspect_schema: 테이블의 컬럼/인덱스/제약조건 조회
- generate_er_diagram: 스키마의 ER 다이어그램(Mermaid) 생성
- advise_index: 쿼리 분석 기반 인덱스 추천

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11
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
from app.framework.dbutil import DBProvider, resolve_engine

AGENT_TYPE = "schema_expert"

_VALID_COMMANDS = frozenset({"generate_ddl", "inspect_schema", "generate_er_diagram", "advise_index"})

# Required fields per sub_command
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "generate_ddl": ["table_name", "columns"],
    "inspect_schema": ["table"],
    "generate_er_diagram": [],
    "advise_index": ["query"],
}


class SchemaExpertInput(BaseModel):
    """Schema Expert Agent 입력 스키마."""

    sub_command: str = Field(
        ..., description="실행할 서브커맨드: generate_ddl | inspect_schema | generate_er_diagram | advise_index"
    )
    table_name: str = Field(default="", description="테이블명 (generate_ddl용)")
    columns: list[dict] = Field(default_factory=list, description="컬럼 명세 목록 (generate_ddl용)")
    schema_name: str = Field(default="public", description="스키마명 (inspect_schema, generate_er_diagram용)")
    table: str = Field(default="", description="조회할 테이블명 (inspect_schema용)")
    query: str = Field(default="", description="쿼리 (advise_index용)")
    if_not_exists: bool = Field(default=True, description="IF NOT EXISTS 포함 여부 (generate_ddl용)")


class SchemaExpertTool(BaseAgentTool):
    """통합 Schema Expert Agent Tool.

    sub_command에 따라 적절한 내부 핸들러로 라우팅합니다.
    단일 DBProvider 인스턴스를 공유합니다.
    """

    db_provider: DBProvider | None = Field(default=None, exclude=True)
    name: str = "schema_expert"
    description: str = (
        "DB 스키마 관련 작업을 수행합니다. generate_ddl(DDL 생성), inspect_schema(스키마 조회), "
        "generate_er_diagram(ER 다이어그램 생성), advise_index(인덱스 추천)를 지원합니다."
    )
    args_schema: type[BaseModel] = SchemaExpertInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(
        self,
        sub_command: str,
        table_name: str = "",
        columns: list[dict] | None = None,
        schema_name: str = "public",
        table: str = "",
        query: str = "",
        if_not_exists: bool = True,
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("비동기(_arun)로만 실행됩니다")

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="Schema Expert 실행 중 오류가 발생했습니다")
    async def _arun(
        self,
        sub_command: str,
        table_name: str = "",
        columns: list[dict] | None = None,
        schema_name: str = "public",
        table: str = "",
        query: str = "",
        if_not_exists: bool = True,
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

        # 입력 필드 검증
        missing = self._validate_inputs(
            sub_command,
            table_name=table_name,
            columns=columns,
            table=table,
            query=query,
        )
        if missing:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message=f"필수 입력 필드가 누락되었습니다: {missing}",
                error_detail=f"sub_command '{sub_command}'에 필요한 필드: {_REQUIRED_FIELDS[sub_command]}",
                sub_command=sub_command,
                missing_fields=missing,
                accepted_fields=_REQUIRED_FIELDS[sub_command],
            )

        # 핸들러 디스패치
        handler = getattr(self, f"_handle_{sub_command}")
        return await handler(
            table_name=table_name,
            columns=columns or [],
            schema_name=schema_name,
            table=table,
            query=query,
            if_not_exists=if_not_exists,
        )

    def _validate_inputs(
        self,
        sub_command: str,
        table_name: str = "",
        columns: list[dict] | None = None,
        table: str = "",
        query: str = "",
    ) -> list[str]:
        """서브커맨드별 필수 입력 필드를 검증합니다."""
        missing = []
        required = _REQUIRED_FIELDS.get(sub_command, [])
        field_values = {
            "table_name": table_name,
            "columns": columns,
            "table": table,
            "query": query,
        }
        for field in required:
            val = field_values.get(field)
            if val is None or val == "" or val == []:
                missing.append(field)
        return missing

    async def _handle_generate_ddl(self, table_name: str, columns: list[dict], if_not_exists: bool = True, **kwargs: Any) -> tuple[str, dict]:
        """generate_ddl 서브커맨드: 컬럼 명세로부터 CREATE TABLE DDL 생성."""
        from app.tool_agents.ddl_generator_agent.tool import ColumnSpec, DDLGenInput, generate_ddl

        col_specs = [ColumnSpec(**col) for col in columns]
        spec = DDLGenInput(
            table_name=table_name,
            columns=col_specs,
            schema_name=kwargs.get("schema_name", "public"),
            if_not_exists=if_not_exists,
        )
        result = generate_ddl(spec)
        return result["full_ddl"], build_artifact(AGENT_TYPE, sub_command="generate_ddl", **result)

    async def _handle_inspect_schema(self, table: str, schema_name: str = "public", **kwargs: Any) -> tuple[str, dict]:
        """inspect_schema 서브커맨드: 테이블 컬럼/인덱스/제약조건 조회."""
        from app.framework.dbutil import fetch_all

        db = self._get_db()
        if resolve_engine(db) is None:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message="데이터베이스에 연결할 수 없습니다.",
                note="database_unavailable",
                sub_command="inspect_schema",
            )

        from app.tool_agents.schema_inspector_agent.tool import (
            _COLUMNS_SQL,
            _CONSTRAINTS_SQL,
            _INDEXES_SQL,
        )

        params = {"schema": schema_name, "table": table}
        columns = await fetch_all(db, _COLUMNS_SQL, params)
        indexes = await fetch_all(db, _INDEXES_SQL, params)
        constraints = await fetch_all(db, _CONSTRAINTS_SQL, params)

        return "", build_artifact(
            AGENT_TYPE,
            sub_command="inspect_schema",
            table=table,
            schema=schema_name,
            exists=bool(columns),
            columns=columns,
            indexes=indexes,
            constraints=constraints,
        )

    async def _handle_generate_er_diagram(self, schema_name: str = "public", **kwargs: Any) -> tuple[str, dict]:
        """generate_er_diagram 서브커맨드: Mermaid ER 다이어그램 생성."""
        from app.framework.dbutil import fetch_all
        from app.tool_agents.er_diagram_agent.tool import (
            _COLUMNS_SQL,
            _FK_SQL,
            build_mermaid_erd,
        )

        db = self._get_db()
        if resolve_engine(db) is None:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message="데이터베이스에 연결할 수 없습니다.",
                note="database_unavailable",
                sub_command="generate_er_diagram",
            )

        columns = await fetch_all(db, _COLUMNS_SQL, {"schema": schema_name})
        fks = await fetch_all(db, _FK_SQL, {"schema": schema_name})
        mermaid = build_mermaid_erd(columns, fks)
        table_count = len({c["table_name"] for c in columns})

        return "", build_artifact(
            AGENT_TYPE,
            sub_command="generate_er_diagram",
            schema=schema_name,
            mermaid=mermaid,
            table_count=table_count,
            fk_count=len(fks),
        )

    async def _handle_advise_index(self, query: str, **kwargs: Any) -> tuple[str, dict]:
        """advise_index 서브커맨드: 쿼리 분석 기반 인덱스 추천."""
        from app.tool_agents.index_advisor_agent.tool import recommend_indexes

        recs = recommend_indexes(query)

        # DB 가용 시 Seq Scan 확인
        seq_scan = await self._check_seq_scan(query)

        return "", build_artifact(
            AGENT_TYPE,
            sub_command="advise_index",
            recommendations=recs,
            seq_scan_detected=seq_scan,
        )

    async def _check_seq_scan(self, query: str) -> bool | None:
        """DB가 가용하면 EXPLAIN으로 Seq Scan 여부를 확인합니다."""
        from app.framework.dbutil import fetch_all

        db = self._get_db()
        if resolve_engine(db) is None:
            return None
        try:
            rows = await fetch_all(db, f"EXPLAIN (FORMAT TEXT) {query}")
            plan_text = "\n".join(str(v) for r in rows for v in r.values())
            return "Seq Scan" in plan_text
        except Exception:  # noqa: BLE001
            return None

    def _get_db(self) -> Any:
        """공유 DBProvider를 통해 DB 인스턴스를 획득합니다."""
        return self.db_provider() if self.db_provider else None
