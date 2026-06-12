"""Data Quality Agent Tool 구현.

규칙(not_null, unique, range, accepted_values, non_negative)별로 위반 행 수를
집계하여 데이터 품질 검사 결과를 반환합니다. 식별자는 안전하게 따옴표 처리하고
값은 바인드 파라미터로 전달합니다.
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

AGENT_TYPE = "data_quality_agent"

CheckType = Literal["not_null", "unique", "range", "accepted_values", "non_negative"]


class QualityRule(BaseModel):
    check: CheckType = Field(..., description="검사 유형")
    column: str = Field(..., description="대상 컬럼")
    min: float | None = Field(default=None, description="range 검사 최소값")
    max: float | None = Field(default=None, description="range 검사 최대값")
    values: list[str] | None = Field(default=None, description="accepted_values 허용 목록")


class DataQualityInput(BaseModel):
    table: str = Field(..., description="검사할 테이블명")
    schema_name: str = Field(default="public", description="스키마명")
    rules: list[QualityRule] = Field(..., description="적용할 품질 규칙 목록")


def build_violation_query(fq: str, rule: QualityRule) -> tuple[str, dict]:
    """규칙에 대한 위반 행 수 카운트 쿼리와 파라미터를 생성합니다."""
    col = quote_ident(rule.column)
    if rule.check == "not_null":
        return f"SELECT COUNT(*) AS violations FROM {fq} WHERE {col} IS NULL", {}
    if rule.check == "non_negative":
        return f"SELECT COUNT(*) AS violations FROM {fq} WHERE {col} < 0", {}
    if rule.check == "unique":
        return (
            f"SELECT COALESCE(SUM(cnt) - COUNT(*), 0) AS violations FROM "
            f"(SELECT {col} AS v, COUNT(*) AS cnt FROM {fq} "
            f"GROUP BY {col} HAVING COUNT(*) > 1) dup",
            {},
        )
    if rule.check == "range":
        conds, params = [], {}
        if rule.min is not None:
            conds.append(f"{col} < :rmin")
            params["rmin"] = rule.min
        if rule.max is not None:
            conds.append(f"{col} > :rmax")
            params["rmax"] = rule.max
        where = " OR ".join(conds) if conds else "FALSE"
        return f"SELECT COUNT(*) AS violations FROM {fq} WHERE {where}", params
    if rule.check == "accepted_values":
        values = rule.values or []
        if not values:
            return f"SELECT 0 AS violations", {}
        placeholders = ", ".join(f":v{i}" for i in range(len(values)))
        params = {f"v{i}": v for i, v in enumerate(values)}
        return (
            f"SELECT COUNT(*) AS violations FROM {fq} "
            f"WHERE {col} IS NOT NULL AND {col}::text NOT IN ({placeholders})",
            params,
        )
    raise ValueError(f"알 수 없는 검사 유형: {rule.check}")


class DataQualityTool(BaseAgentTool):
    db_provider: DBProvider | None = Field(default=None, exclude=True)
    name: str = "check_data_quality"
    description: str = (
        "테이블에 대해 규칙 기반 데이터 품질 검사(not_null, unique, range, "
        "accepted_values, non_negative)를 수행하고 위반 건수를 보고합니다."
    )
    args_schema: type[BaseModel] = DataQualityInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, table: str, rules: list, schema_name: str = "public", config=None):
        raise NotImplementedError("비동기(_arun)로만 실행됩니다")

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="데이터 품질 검사 중 오류가 발생했습니다", results=[])
    async def _arun(
        self,
        table: str,
        rules: list,
        schema_name: str = "public",
        config: RunnableConfig | None = None,
    ):
        db = self.db_provider() if self.db_provider else None
        if resolve_engine(db) is None:
            return "", build_artifact(AGENT_TYPE, note="database_unavailable", results=[])

        fq = qualified_table(table, schema_name)
        parsed_rules = [r if isinstance(r, QualityRule) else QualityRule(**r) for r in rules]

        results = []
        for rule in parsed_rules:
            sql, params = build_violation_query(fq, rule)
            rows = await fetch_all(db, sql, params)
            violations = int(rows[0]["violations"]) if rows else 0
            results.append(
                {
                    "check": rule.check,
                    "column": rule.column,
                    "violations": violations,
                    "passed": violations == 0,
                }
            )

        passed = sum(1 for r in results if r["passed"])
        return "", build_artifact(
            AGENT_TYPE, table=table, schema=schema_name,
            results=results, passed=passed, failed=len(results) - passed,
        )

    def format_content(self, message: ToolMessage) -> ToolMessage:
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if art.get("note") == "database_unavailable":
            return message.model_copy(update={"content": "데이터베이스에 연결할 수 없습니다."})
        results = art.get("results", [])
        if not results:
            return message.model_copy(update={"content": "적용된 검사 규칙이 없습니다."})
        lines = [f"품질 검사: {art.get('passed')}개 통과 / {art.get('failed')}개 실패"]
        for r in results:
            status = "✅" if r["passed"] else "❌"
            lines.append(f"  {status} {r['check']}({r['column']}): 위반 {r['violations']}건")
        return message.model_copy(update={"content": "\n".join(lines)})
