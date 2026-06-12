"""SQL Formatter Agent Tool 구현.

키워드 대문자화 + 주요 절(clause) 줄바꿈/들여쓰기로 SQL을 읽기 좋게 정렬합니다.
외부 의존성 없이 정규식 기반으로 동작합니다.
"""

from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact

AGENT_TYPE = "sql_formatter_agent"

# 새 줄로 분리할 주요 절 키워드
_NEWLINE_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "GROUP BY", "HAVING", "ORDER BY",
    "LIMIT", "OFFSET", "UNION ALL", "UNION", "INTERSECT", "EXCEPT",
    "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "FULL JOIN", "CROSS JOIN", "JOIN",
    "ON", "VALUES", "SET", "INSERT INTO", "UPDATE", "DELETE FROM",
]

# 대문자화할 일반 키워드
_UPPER_KEYWORDS = [
    "select", "from", "where", "group by", "having", "order by", "limit",
    "offset", "join", "left join", "right join", "inner join", "full join",
    "cross join", "on", "and", "or", "not", "in", "like", "between", "is",
    "null", "as", "distinct", "count", "sum", "avg", "min", "max", "case",
    "when", "then", "else", "end", "asc", "desc", "union", "all", "insert",
    "into", "values", "update", "set", "delete", "create", "table", "exists",
]


def format_sql(sql: str, indent: str = "  ") -> str:
    """SQL을 정렬/포맷합니다.

    Args:
        sql: 원본 SQL 문자열.
        indent: 들여쓰기 단위.

    Returns:
        포맷된 SQL.
    """
    # 1. 공백 정규화
    text = re.sub(r"\s+", " ", sql.strip().rstrip(";"))

    # 2. 키워드 대문자화 (단어 경계 기준, 긴 것부터)
    for kw in sorted(_UPPER_KEYWORDS, key=len, reverse=True):
        text = re.sub(
            rf"(?<![\w.]){re.escape(kw)}(?![\w])",
            kw.upper(),
            text,
            flags=re.IGNORECASE,
        )

    # 3. 주요 절 앞에 줄바꿈 (긴 키워드부터 처리해 부분 매칭 방지)
    for kw in sorted(_NEWLINE_KEYWORDS, key=len, reverse=True):
        text = re.sub(rf"(?<![\w]){re.escape(kw)}(?![\w])", f"\n{kw}", text)

    # 4. 줄 단위 정리 + SELECT 컬럼 들여쓰기
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    formatted: list[str] = []
    for line in lines:
        if line.upper().startswith("SELECT"):
            cols = line[len("SELECT"):].strip()
            formatted.append("SELECT")
            for i, col in enumerate(_split_columns(cols)):
                comma = "," if i < len(_split_columns(cols)) - 1 else ""
                formatted.append(f"{indent}{col.strip()}{comma}")
        else:
            formatted.append(line)
    return "\n".join(formatted) + ";"


def _split_columns(cols: str) -> list[str]:
    """괄호 깊이를 고려하여 SELECT 컬럼 목록을 콤마로 분리합니다."""
    result: list[str] = []
    depth = 0
    current = ""
    for ch in cols:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            result.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        result.append(current)
    return result or [cols]


class SqlFormatterInput(BaseModel):
    sql: str = Field(..., description="포맷할 SQL 쿼리")


class SqlFormatterTool(BaseAgentTool):
    name: str = "format_sql"
    description: str = (
        "SQL 쿼리를 읽기 좋게 정렬/포맷합니다. 키워드 대문자화, 절 줄바꿈, "
        "컬럼 들여쓰기를 적용합니다."
    )
    args_schema: type[BaseModel] = SqlFormatterInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(self, sql: str, config: RunnableConfig | None = None):
        return self._format(sql)

    async def _arun(self, sql: str, config: RunnableConfig | None = None):
        return self._format(sql)

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="SQL 포맷 중 오류가 발생했습니다")
    def _format(self, sql: str) -> tuple[str, dict]:
        formatted = format_sql(sql)
        return formatted, build_artifact(AGENT_TYPE, formatted_sql=formatted, original=sql)

    def format_content(self, message: ToolMessage) -> ToolMessage:
        if isinstance(message.artifact, dict) and "formatted_sql" in message.artifact:
            sql = message.artifact["formatted_sql"]
            return message.model_copy(update={"content": f"```sql\n{sql}\n```"})
        return message
