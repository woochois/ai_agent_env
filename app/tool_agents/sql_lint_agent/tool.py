"""SQL Lint Agent Tool 구현.

규칙 기반으로 SQL의 안티패턴/위험 패턴을 검출합니다. 각 발견 항목은
severity(warning/error)와 설명, 권고를 포함합니다.
"""

from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact

AGENT_TYPE = "sql_lint_agent"


def lint_sql(sql: str) -> list[dict]:
    """SQL을 검사하여 발견 항목 목록을 반환합니다.

    Returns:
        ``[{"rule", "severity", "message", "suggestion"}]`` 형태의 리스트.
    """
    findings: list[dict] = []
    normalized = re.sub(r"\s+", " ", sql.strip())
    upper = normalized.upper()

    def add(rule: str, severity: str, message: str, suggestion: str) -> None:
        findings.append(
            {"rule": rule, "severity": severity, "message": message, "suggestion": suggestion}
        )

    # 1. SELECT *
    if re.search(r"SELECT\s+\*", upper):
        add(
            "select_star", "warning",
            "SELECT * 사용이 감지되었습니다.",
            "필요한 컬럼만 명시하세요. 불필요한 I/O와 인덱스 미사용을 유발할 수 있습니다.",
        )

    # 2. WHERE 없는 UPDATE/DELETE
    if re.search(r"\bUPDATE\b", upper) and "WHERE" not in upper:
        add(
            "update_without_where", "error",
            "WHERE 절 없는 UPDATE 입니다. 전체 행이 갱신될 수 있습니다.",
            "갱신 대상을 한정하는 WHERE 절을 추가하세요.",
        )
    if re.search(r"\bDELETE\s+FROM\b", upper) and "WHERE" not in upper:
        add(
            "delete_without_where", "error",
            "WHERE 절 없는 DELETE 입니다. 전체 행이 삭제될 수 있습니다.",
            "삭제 대상을 한정하는 WHERE 절을 추가하거나 TRUNCATE 의도를 확인하세요.",
        )

    # 3. 선행 와일드카드 LIKE
    if re.search(r"LIKE\s+'%", upper):
        add(
            "leading_wildcard_like", "warning",
            "선행 와일드카드 LIKE ('%...')가 감지되었습니다.",
            "B-tree 인덱스를 활용할 수 없습니다. 전문검색(FTS)이나 trigram 인덱스를 고려하세요.",
        )

    # 4. NOT IN (서브쿼리)
    if re.search(r"NOT\s+IN\s*\(", upper):
        add(
            "not_in_subquery", "warning",
            "NOT IN 사용이 감지되었습니다.",
            "서브쿼리에 NULL이 포함되면 결과가 비어버립니다. NOT EXISTS 사용을 권장합니다.",
        )

    # 5. WHERE 절 함수 적용 (인덱스 무력화)
    if re.search(r"WHERE\s+\w*\s*\(?\s*(UPPER|LOWER|TRIM|CAST|TO_CHAR|DATE)\s*\(", upper):
        add(
            "function_on_column", "warning",
            "WHERE 절에서 컬럼에 함수를 적용하고 있습니다.",
            "인덱스가 무력화될 수 있습니다. 함수 기반 인덱스 또는 표현식 재작성을 검토하세요.",
        )

    # 6. != 사용 (표준은 <>)
    if "!=" in normalized:
        add(
            "non_standard_inequality", "warning",
            "비표준 부등호 '!=' 사용이 감지되었습니다.",
            "표준 SQL 부등호 '<>' 사용을 권장합니다.",
        )

    # 7. ORDER BY 위치 인덱스 (ORDER BY 1)
    if re.search(r"ORDER\s+BY\s+\d", upper):
        add(
            "order_by_ordinal", "warning",
            "ORDER BY에 위치 인덱스(숫자)를 사용하고 있습니다.",
            "컬럼명을 명시하면 가독성과 유지보수성이 향상됩니다.",
        )

    return findings


class SqlLintInput(BaseModel):
    sql: str = Field(..., description="검사할 SQL 쿼리")


class SqlLintTool(BaseAgentTool):
    name: str = "lint_sql"
    description: str = (
        "SQL의 안티패턴과 위험 패턴(SELECT *, WHERE 없는 DELETE, 선행 와일드카드 등)을 "
        "검출하고 개선안을 제시합니다."
    )
    args_schema: type[BaseModel] = SqlLintInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(self, sql: str, config: RunnableConfig | None = None):
        return self._lint(sql)

    async def _arun(self, sql: str, config: RunnableConfig | None = None):
        return self._lint(sql)

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="SQL 린트 중 오류가 발생했습니다", findings=[])
    def _lint(self, sql: str) -> tuple[str, dict]:
        findings = lint_sql(sql)
        errors = sum(1 for f in findings if f["severity"] == "error")
        warnings = sum(1 for f in findings if f["severity"] == "warning")
        return "", build_artifact(
            AGENT_TYPE, findings=findings, error_count=errors, warning_count=warnings
        )

    def format_content(self, message: ToolMessage) -> ToolMessage:
        if not isinstance(message.artifact, dict):
            return message
        findings = message.artifact.get("findings", [])
        if not findings:
            return message.model_copy(update={"content": "린트 통과: 발견된 문제가 없습니다."})
        lines = [
            f"[{f['severity'].upper()}] {f['message']} → {f['suggestion']}"
            for f in findings
        ]
        return message.model_copy(update={"content": "\n".join(lines)})
