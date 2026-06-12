"""Query Explain Agent Tool 구현.

``EXPLAIN (FORMAT JSON)``으로 쿼리 실행계획을 얻고, 비용/스캔 방식 등 핵심 지표를
추출합니다. 기본은 ANALYZE 미사용(쿼리를 실제 실행하지 않음)이며, ANALYZE는
SELECT 쿼리에만 허용합니다.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact
from app.framework.dbutil import DBProvider, fetch_all, resolve_engine

AGENT_TYPE = "query_explain_agent"


def collect_plan_nodes(node: dict, acc: list[dict]) -> None:
    """플랜 트리를 순회하며 노드 유형/비용을 수집합니다."""
    acc.append(
        {
            "node_type": node.get("Node Type"),
            "relation": node.get("Relation Name"),
            "total_cost": node.get("Total Cost"),
            "plan_rows": node.get("Plan Rows"),
        }
    )
    for child in node.get("Plans", []):
        collect_plan_nodes(child, acc)


def analyze_plan(plan_json: list) -> dict:
    """EXPLAIN JSON 결과에서 핵심 지표와 경고를 추출합니다."""
    root = plan_json[0]["Plan"] if plan_json else {}
    nodes: list[dict] = []
    collect_plan_nodes(root, nodes)

    seq_scans = [n for n in nodes if n["node_type"] == "Seq Scan"]
    warnings = []
    if seq_scans:
        rels = ", ".join(n["relation"] or "?" for n in seq_scans)
        warnings.append(f"Seq Scan 감지: {rels} (인덱스 활용 여부를 검토하세요)")

    return {
        "total_cost": root.get("Total Cost"),
        "estimated_rows": root.get("Plan Rows"),
        "node_count": len(nodes),
        "nodes": nodes,
        "seq_scan_count": len(seq_scans),
        "warnings": warnings,
    }


class QueryExplainInput(BaseModel):
    query: str = Field(..., description="분석할 SQL 쿼리")
    analyze: bool = Field(
        default=False, description="실제 실행 통계 포함 여부(ANALYZE). SELECT만 허용."
    )


class QueryExplainTool(BaseAgentTool):
    db_provider: DBProvider | None = Field(default=None, exclude=True)
    name: str = "explain_query"
    description: str = (
        "쿼리의 실행계획(EXPLAIN)을 분석하여 예상 비용, 스캔 방식, Seq Scan 경고 등을 제공합니다."
    )
    args_schema: type[BaseModel] = QueryExplainInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(self, query: str, analyze: bool = False, config=None):
        raise NotImplementedError("비동기(_arun)로만 실행됩니다")

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="실행계획 분석 중 오류가 발생했습니다")
    async def _arun(self, query: str, analyze: bool = False, config: RunnableConfig | None = None):
        db = self.db_provider() if self.db_provider else None
        if resolve_engine(db) is None:
            return "", build_artifact(AGENT_TYPE, note="database_unavailable")

        # 안전장치: ANALYZE는 SELECT 쿼리에만 허용 (부작용 방지)
        if analyze and not query.lstrip().upper().startswith("SELECT"):
            return "", build_artifact(
                AGENT_TYPE,
                error_message="ANALYZE는 SELECT 쿼리에만 허용됩니다",
            )

        options = "ANALYZE, FORMAT JSON" if analyze else "FORMAT JSON"
        explain_sql = f"EXPLAIN ({options}) {query}"
        rows = await fetch_all(db, explain_sql)

        # 결과는 단일 행/단일 컬럼의 JSON
        plan_json = _extract_plan(rows)
        analysis = analyze_plan(plan_json)
        return "", build_artifact(AGENT_TYPE, analyzed=analyze, **analysis)

    def format_content(self, message: ToolMessage) -> ToolMessage:
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if art.get("note") == "database_unavailable":
            return message.model_copy(update={"content": "데이터베이스에 연결할 수 없습니다."})
        if "error_message" in art:
            return message.model_copy(update={"content": art["error_message"]})
        lines = [
            f"예상 비용: {art.get('total_cost')}, 예상 행 수: {art.get('estimated_rows')}",
            f"플랜 노드: {art.get('node_count')}개, Seq Scan: {art.get('seq_scan_count')}개",
        ]
        lines.extend(art.get("warnings", []))
        return message.model_copy(update={"content": "\n".join(lines)})


def _extract_plan(rows: list[dict]) -> list:
    """fetch_all 결과에서 EXPLAIN JSON 플랜을 추출합니다."""
    if not rows:
        return []
    value = next(iter(rows[0].values()))
    if isinstance(value, str):
        return json.loads(value)
    return value  # 이미 파싱된 JSON (list)
