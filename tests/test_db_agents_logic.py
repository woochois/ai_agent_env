"""데이터베이스 Agent의 순수 로직 함수 단위 테스트.

DB 연결 없이 검증 가능한 함수들을 테스트합니다.
- SQL 포맷터, 린터, DDL 생성기
- 인덱스 추천 휴리스틱, ERD 빌더, EXPLAIN 플랜 분석, 품질 검사 쿼리 빌더
"""

from __future__ import annotations

from app.tool_agents.data_quality_agent.tool import QualityRule, build_violation_query
from app.tool_agents.ddl_generator_agent.tool import ColumnSpec, DDLGenInput, generate_ddl
from app.tool_agents.er_diagram_agent.tool import build_mermaid_erd
from app.tool_agents.index_advisor_agent.tool import (
    extract_predicate_columns,
    recommend_indexes,
)
from app.tool_agents.query_explain_agent.tool import analyze_plan
from app.tool_agents.sql_formatter_agent.tool import format_sql
from app.tool_agents.sql_lint_agent.tool import lint_sql


# --- SQL Formatter ---


def test_format_sql_uppercases_and_breaks_clauses():
    out = format_sql("select id, name from users where id = 1 order by name")
    assert "SELECT" in out
    assert "\nFROM" in out
    assert "\nWHERE" in out
    assert "\nORDER BY" in out
    assert out.endswith(";")


def test_format_sql_indents_columns():
    out = format_sql("select a, b, c from t")
    lines = out.split("\n")
    # SELECT 다음 줄들은 들여쓰기된 컬럼
    assert lines[0] == "SELECT"
    assert lines[1].startswith("  ")


# --- SQL Lint ---


def test_lint_detects_select_star():
    findings = lint_sql("SELECT * FROM users")
    assert any(f["rule"] == "select_star" for f in findings)


def test_lint_detects_delete_without_where():
    findings = lint_sql("DELETE FROM users")
    rules = {f["rule"]: f for f in findings}
    assert "delete_without_where" in rules
    assert rules["delete_without_where"]["severity"] == "error"


def test_lint_detects_leading_wildcard():
    findings = lint_sql("SELECT id FROM t WHERE name LIKE '%kim'")
    assert any(f["rule"] == "leading_wildcard_like" for f in findings)


def test_lint_clean_query_minimal_findings():
    findings = lint_sql("SELECT id FROM users WHERE id = 1")
    assert all(f["severity"] != "error" for f in findings)


# --- DDL Generator ---


def test_generate_ddl_basic():
    spec = DDLGenInput(
        table_name="users",
        columns=[
            ColumnSpec(name="id", type="UUID", primary_key=True),
            ColumnSpec(name="email", type="VARCHAR(255)", nullable=False, unique=True),
            ColumnSpec(name="created_at", type="TIMESTAMPTZ", default="NOW()"),
        ],
    )
    result = generate_ddl(spec)
    ddl = result["create_table"]
    assert 'CREATE TABLE IF NOT EXISTS "public"."users"' in ddl
    assert '"id" UUID NOT NULL' in ddl
    assert "PRIMARY KEY" in ddl
    assert 'DEFAULT NOW()' in ddl
    # unique 컬럼은 인덱스로 생성
    assert any("UNIQUE INDEX" in idx for idx in result["indexes"])


# --- Index Advisor ---


def test_extract_predicate_columns():
    sql = "SELECT * FROM orders WHERE status = 'A' AND amount > 100 ORDER BY created_at"
    cols = extract_predicate_columns(sql)
    assert "status" in cols["equality"]
    assert "amount" in cols["range"]
    assert "created_at" in cols["order_by"]


def test_recommend_indexes_creates_composite():
    sql = "SELECT id FROM orders WHERE status = 'A' AND amount > 100"
    recs = recommend_indexes(sql)
    assert recs
    assert any("CREATE INDEX" in r["ddl"] for r in recs)
    # 등치(status) + 범위(amount) 복합 인덱스
    assert any(set(["status", "amount"]).issubset(set(r["columns"])) for r in recs)


def test_recommend_indexes_join_keys():
    sql = "SELECT * FROM a JOIN b ON a.bid = b.id WHERE a.x = 1"
    recs = recommend_indexes(sql)
    assert any("join" in r["ddl"] for r in recs)


# --- ER Diagram ---


def test_build_mermaid_erd():
    columns = [
        {"table_name": "users", "column_name": "id", "data_type": "uuid"},
        {"table_name": "orders", "column_name": "id", "data_type": "uuid"},
        {"table_name": "orders", "column_name": "user_id", "data_type": "uuid"},
    ]
    fks = [
        {"from_table": "orders", "from_column": "user_id", "to_table": "users", "to_column": "id"}
    ]
    mermaid = build_mermaid_erd(columns, fks)
    assert mermaid.startswith("erDiagram")
    assert "users {" in mermaid
    assert "orders {" in mermaid
    assert "users ||--o{ orders" in mermaid


# --- Query Explain plan analysis ---


def test_analyze_plan_detects_seq_scan():
    plan_json = [
        {
            "Plan": {
                "Node Type": "Seq Scan",
                "Relation Name": "big_table",
                "Total Cost": 1234.5,
                "Plan Rows": 10000,
                "Plans": [],
            }
        }
    ]
    analysis = analyze_plan(plan_json)
    assert analysis["seq_scan_count"] == 1
    assert analysis["total_cost"] == 1234.5
    assert analysis["warnings"]


def test_analyze_plan_nested_nodes():
    plan_json = [
        {
            "Plan": {
                "Node Type": "Hash Join",
                "Total Cost": 500.0,
                "Plan Rows": 100,
                "Plans": [
                    {"Node Type": "Index Scan", "Total Cost": 10, "Plan Rows": 50, "Plans": []},
                    {"Node Type": "Seq Scan", "Relation Name": "t2", "Total Cost": 200, "Plan Rows": 80, "Plans": []},
                ],
            }
        }
    ]
    analysis = analyze_plan(plan_json)
    assert analysis["node_count"] == 3
    assert analysis["seq_scan_count"] == 1


# --- Data Quality query builder ---


def test_build_violation_query_not_null():
    sql, params = build_violation_query('"public"."t"', QualityRule(check="not_null", column="email"))
    assert "IS NULL" in sql
    assert params == {}


def test_build_violation_query_range():
    sql, params = build_violation_query(
        '"public"."t"', QualityRule(check="range", column="age", min=0, max=120)
    )
    assert ":rmin" in sql and ":rmax" in sql
    assert params == {"rmin": 0, "rmax": 120}


def test_build_violation_query_accepted_values():
    sql, params = build_violation_query(
        '"public"."t"',
        QualityRule(check="accepted_values", column="status", values=["A", "B"]),
    )
    assert "NOT IN" in sql
    assert params == {"v0": "A", "v1": "B"}


def test_build_violation_query_unique():
    sql, _ = build_violation_query('"public"."t"', QualityRule(check="unique", column="email"))
    assert "GROUP BY" in sql and "HAVING" in sql
