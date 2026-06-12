"""Index Advisor Agent Tool 구현.

쿼리에서 WHERE/JOIN/ORDER BY에 사용된 컬럼을 휴리스틱으로 추출하여 인덱스
후보를 추천합니다. DB가 가용하면 EXPLAIN으로 Seq Scan 여부를 추가 확인합니다.
"""

from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact
from app.framework.dbutil import DBProvider, fetch_all, resolve_engine

AGENT_TYPE = "index_advisor_agent"


def _first_table(sql: str) -> str | None:
    """FROM 절의 첫 테이블명을 추출합니다."""
    m = re.search(r"\bFROM\s+([a-zA-Z_][\w.]*)", sql, re.IGNORECASE)
    return m.group(1) if m else None


def extract_predicate_columns(sql: str) -> dict:
    """WHERE/JOIN/ORDER BY에서 인덱스 후보 컬럼을 추출합니다.

    Returns:
        ``{"equality": [...], "range": [...], "order_by": [...], "join": [...]}``
    """
    text = re.sub(r"\s+", " ", sql)

    where_match = re.search(
        r"\bWHERE\b(.*?)(?:\bGROUP BY\b|\bORDER BY\b|\bLIMIT\b|$)", text, re.IGNORECASE
    )
    where_clause = where_match.group(1) if where_match else ""

    def _col(name: str) -> str:
        return name.split(".")[-1].strip().strip('"')

    equality, range_cols = [], []
    for m in re.finditer(r"([a-zA-Z_][\w.]*)\s*(=|>=|<=|>|<|<>|!=|LIKE|IN)\s", where_clause, re.IGNORECASE):
        col, op = _col(m.group(1)), m.group(2).upper()
        if op == "=":
            equality.append(col)
        elif op in (">", "<", ">=", "<=", "LIKE", "IN"):
            range_cols.append(col)

    join_cols = []
    for m in re.finditer(r"\bON\s+([a-zA-Z_][\w.]*)\s*=\s*([a-zA-Z_][\w.]*)", text, re.IGNORECASE):
        join_cols.extend([_col(m.group(1)), _col(m.group(2))])

    order_cols = []
    ob = re.search(r"\bORDER BY\b(.*?)(?:\bLIMIT\b|$)", text, re.IGNORECASE)
    if ob:
        for part in ob.group(1).split(","):
            token = part.strip().split()[0] if part.strip() else ""
            if token:
                order_cols.append(_col(token))

    return {
        "equality": _dedup(equality),
        "range": _dedup(range_cols),
        "order_by": _dedup(order_cols),
        "join": _dedup(join_cols),
    }


def _dedup(items: list[str]) -> list[str]:
    seen, result = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def recommend_indexes(sql: str) -> list[dict]:
    """추출된 컬럼으로부터 인덱스 추천 목록을 생성합니다."""
    table = _first_table(sql) or "your_table"
    cols = extract_predicate_columns(sql)
    recs: list[dict] = []

    # 등치 + 범위 복합 인덱스 (등치 컬럼 먼저, 범위 컬럼 마지막)
    composite = cols["equality"] + [c for c in cols["range"] if c not in cols["equality"]]
    if composite:
        col_list = ", ".join(composite)
        recs.append(
            {
                "columns": composite,
                "rationale": "WHERE 절 등치/범위 조건 컬럼. 복합 인덱스로 필터링을 가속합니다.",
                "ddl": f"CREATE INDEX idx_{table}_{'_'.join(composite)} ON {table} ({col_list});",
            }
        )

    # ORDER BY 인덱스
    if cols["order_by"]:
        col_list = ", ".join(cols["order_by"])
        recs.append(
            {
                "columns": cols["order_by"],
                "rationale": "ORDER BY 정렬 비용을 줄이기 위한 인덱스.",
                "ddl": f"CREATE INDEX idx_{table}_{'_'.join(cols['order_by'])}_sort ON {table} ({col_list});",
            }
        )

    # JOIN 컬럼 인덱스
    for jc in cols["join"]:
        recs.append(
            {
                "columns": [jc],
                "rationale": "JOIN 키 컬럼. 조인 성능 향상을 위해 인덱스를 권장합니다.",
                "ddl": f"CREATE INDEX idx_{table}_{jc}_join ON {table} ({jc});",
            }
        )

    return recs


class IndexAdvisorInput(BaseModel):
    query: str = Field(..., description="인덱스를 추천받을 SELECT 쿼리")


class IndexAdvisorTool(BaseAgentTool):
    db_provider: DBProvider | None = Field(default=None, exclude=True)
    name: str = "advise_indexes"
    description: str = (
        "쿼리의 WHERE/JOIN/ORDER BY 컬럼을 분석하여 인덱스 후보와 CREATE INDEX DDL을 추천합니다."
    )
    args_schema: type[BaseModel] = IndexAdvisorInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, query: str, config=None):
        return self._advise_sync(query)

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="인덱스 추천 중 오류가 발생했습니다", recommendations=[])
    def _advise_sync(self, query: str) -> tuple[str, dict]:
        recs = recommend_indexes(query)
        return "", build_artifact(AGENT_TYPE, recommendations=recs, seq_scan_detected=None)

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="인덱스 추천 중 오류가 발생했습니다", recommendations=[])
    async def _arun(self, query: str, config: RunnableConfig | None = None):
        recs = recommend_indexes(query)
        seq_scan = await self._check_seq_scan(query)
        return "", build_artifact(AGENT_TYPE, recommendations=recs, seq_scan_detected=seq_scan)

    async def _check_seq_scan(self, query: str) -> bool | None:
        """DB가 가용하면 EXPLAIN으로 Seq Scan 여부를 확인합니다 (실패 시 None)."""
        db = self.db_provider() if self.db_provider else None
        if resolve_engine(db) is None:
            return None
        try:
            rows = await fetch_all(db, f"EXPLAIN (FORMAT TEXT) {query}")
            plan_text = "\n".join(str(v) for r in rows for v in r.values())
            return "Seq Scan" in plan_text
        except Exception:  # noqa: BLE001 - EXPLAIN 실패는 추천에 영향 없음
            return None

    def format_content(self, message: ToolMessage) -> ToolMessage:
        art = message.artifact if isinstance(message.artifact, dict) else {}
        recs = art.get("recommendations", [])
        if not recs:
            return message.model_copy(
                update={"content": "추천할 인덱스가 없습니다 (WHERE/JOIN/ORDER BY 조건 없음)."}
            )
        lines = []
        if art.get("seq_scan_detected"):
            lines.append("⚠️ EXPLAIN에서 Seq Scan이 감지되었습니다.")
        for r in recs:
            lines.append(f"{r['ddl']}\n  → {r['rationale']}")
        return message.model_copy(update={"content": "\n".join(lines)})
