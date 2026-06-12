"""scripts/init.sql 스키마 초기화 멱등성 Property 기반 테스트.

Hypothesis를 사용하여 스키마 초기화 스크립트의 멱등성을 검증합니다.
SQLite를 사용하여 CREATE TABLE IF NOT EXISTS 의미론을 시뮬레이션합니다.
"""

# Feature: docker-ai-agent-dev-env, Property 6: 스키마 초기화 멱등성

import os
import re
import sqlite3
import uuid

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# --- SQL 스크립트 파싱 및 SQLite 호환 변환 ---

INIT_SQL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "scripts", "init.sql"
)


def load_init_sql() -> str:
    """init.sql 스크립트를 로드합니다."""
    with open(INIT_SQL_PATH, "r", encoding="utf-8") as f:
        return f.read()


def convert_to_sqlite(sql: str) -> list[str]:
    """PostgreSQL SQL을 SQLite 호환 형태로 변환합니다.

    변환 내용:
    - DEFAULT gen_random_uuid() 제거 (순서 중요: UUID 타입 변환 전에 처리)
    - UUID -> TEXT
    - VARCHAR(N) -> TEXT
    - JSONB -> TEXT
    - TIMESTAMP WITH TIME ZONE -> TEXT
    - NOW() -> CURRENT_TIMESTAMP
    - CHECK 제약조건 유지
    - CREATE INDEX IF NOT EXISTS 유지
    """
    # 주석 라인 제거
    lines = sql.split("\n")
    lines = [line for line in lines if not line.strip().startswith("--")]
    sql_clean = "\n".join(lines)

    # 순서 중요: gen_random_uuid()를 먼저 제거해야 UUID 타입 변환에 영향 없음
    sql_clean = re.sub(
        r"DEFAULT\s+gen_random_uuid\(\)", "", sql_clean, flags=re.IGNORECASE
    )
    sql_clean = re.sub(
        r"TIMESTAMP\s+WITH\s+TIME\s+ZONE", "TEXT", sql_clean, flags=re.IGNORECASE
    )
    sql_clean = re.sub(r"NOW\(\)", "CURRENT_TIMESTAMP", sql_clean, flags=re.IGNORECASE)
    sql_clean = re.sub(r"\bUUID\b", "TEXT", sql_clean, flags=re.IGNORECASE)
    sql_clean = re.sub(r"VARCHAR\(\d+\)", "TEXT", sql_clean, flags=re.IGNORECASE)
    sql_clean = re.sub(r"\bJSONB\b", "TEXT", sql_clean, flags=re.IGNORECASE)

    # 세미콜론으로 문장 분리
    statements = [s.strip() for s in sql_clean.split(";") if s.strip()]
    return statements


def execute_init_schema(conn: sqlite3.Connection) -> None:
    """변환된 init.sql을 SQLite 커넥션에서 실행합니다."""
    sql = load_init_sql()
    statements = convert_to_sqlite(sql)
    cursor = conn.cursor()
    for stmt in statements:
        cursor.execute(stmt)
    conn.commit()


def get_schema_info(conn: sqlite3.Connection) -> dict:
    """현재 DB의 스키마 정보를 딕셔너리로 반환합니다."""
    cursor = conn.cursor()

    # 테이블 목록
    cursor.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0]: row[1] for row in cursor.fetchall()}

    # 인덱스 목록
    cursor.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name"
    )
    indexes = {row[0]: row[1] for row in cursor.fetchall()}

    return {"tables": tables, "indexes": indexes}


def get_all_data(conn: sqlite3.Connection) -> dict:
    """모든 테이블의 데이터를 딕셔너리로 반환합니다."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    table_names = [row[0] for row in cursor.fetchall()]

    data = {}
    for table_name in table_names:
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY id")
        rows = cursor.fetchall()
        data[table_name] = rows

    return data


# --- Hypothesis 전략 ---

# 대화 기록 데이터 생성 전략
conversation_strategy = st.fixed_dictionaries({
    "id": st.from_type(type).flatmap(lambda _: st.just(str(uuid.uuid4()))),
    "session_id": st.text(
        alphabet=st.characters(min_codepoint=48, max_codepoint=122),
        min_size=1,
        max_size=36,
    ),
    "role": st.sampled_from(["user", "assistant", "system"]),
    "content": st.text(min_size=1, max_size=200),
    "metadata": st.just("{}"),
    "created_at": st.just("2024-01-01T00:00:00+00:00"),
})

# 문서 메타데이터 생성 전략
document_strategy = st.fixed_dictionaries({
    "id": st.from_type(type).flatmap(lambda _: st.just(str(uuid.uuid4()))),
    "title": st.text(min_size=1, max_size=100),
    "source": st.one_of(st.none(), st.text(min_size=1, max_size=200)),
    "doc_type": st.one_of(st.none(), st.sampled_from(["pdf", "html", "txt", "md"])),
    "chunk_count": st.integers(min_value=0, max_value=1000),
    "indexed_at": st.just("2024-01-01T00:00:00+00:00"),
    "metadata": st.just("{}"),
})

# 스키마 초기화 반복 횟수 전략 (2~5회)
init_count_strategy = st.integers(min_value=2, max_value=5)


# --- Property 테스트 ---


@settings(max_examples=10)
@given(
    conversations=st.lists(conversation_strategy, min_size=0, max_size=5),
    documents=st.lists(document_strategy, min_size=0, max_size=5),
    init_count=init_count_strategy,
)
def test_schema_init_idempotency(conversations, documents, init_count):
    """Property 6: 스키마 초기화 멱등성.

    빈 DB 또는 이미 초기화된 DB에서 스키마 초기화를 여러 번 실행해도
    최종 스키마가 동일하고 기존 데이터가 보존되어야 한다.

    **Validates: Requirements 6.6**
    """
    # 1) 인메모리 SQLite DB 생성
    conn = sqlite3.connect(":memory:")

    try:
        # 2) 최초 스키마 초기화
        execute_init_schema(conn)
        schema_after_first = get_schema_info(conn)

        # 3) 기존 데이터 삽입
        cursor = conn.cursor()
        for conv in conversations:
            cursor.execute(
                "INSERT INTO conversations (id, session_id, role, content, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    conv["id"],
                    conv["session_id"],
                    conv["role"],
                    conv["content"],
                    conv["metadata"],
                    conv["created_at"],
                ),
            )
        for doc in documents:
            cursor.execute(
                "INSERT INTO document_metadata (id, title, source, doc_type, chunk_count, indexed_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    doc["id"],
                    doc["title"],
                    doc["source"],
                    doc["doc_type"],
                    doc["chunk_count"],
                    doc["indexed_at"],
                    doc["metadata"],
                ),
            )
        conn.commit()

        # 4) 데이터 삽입 후 상태 기록
        data_before = get_all_data(conn)

        # 5) 스키마 초기화를 여러 번 반복 실행
        for _ in range(init_count):
            execute_init_schema(conn)

        # 6) 검증: 스키마가 최초 초기화와 동일한지 확인
        schema_after_repeated = get_schema_info(conn)
        assert schema_after_first == schema_after_repeated, (
            f"스키마가 반복 초기화 후 변경됨.\n"
            f"최초: {schema_after_first}\n"
            f"반복 후: {schema_after_repeated}"
        )

        # 7) 검증: 기존 데이터가 보존되는지 확인
        data_after = get_all_data(conn)
        assert data_before == data_after, (
            f"기존 데이터가 반복 초기화 후 손실됨.\n"
            f"이전: {data_before}\n"
            f"이후: {data_after}"
        )

    finally:
        conn.close()


@settings(max_examples=10)
@given(init_count=st.integers(min_value=1, max_value=10))
def test_schema_init_on_empty_db_is_stable(init_count):
    """Property 6 보조: 빈 DB에서의 스키마 초기화 안정성.

    빈 DB에서 스키마 초기화를 N번 실행해도 결과 스키마가 항상 동일해야 한다.

    **Validates: Requirements 6.6**
    """
    conn = sqlite3.connect(":memory:")

    try:
        # 첫 번째 초기화 후 스키마 기록
        execute_init_schema(conn)
        expected_schema = get_schema_info(conn)

        # N-1번 추가 초기화
        for _ in range(init_count - 1):
            execute_init_schema(conn)

        actual_schema = get_schema_info(conn)
        assert expected_schema == actual_schema, (
            f"빈 DB에서 {init_count}번 초기화 후 스키마가 다름.\n"
            f"기대: {expected_schema}\n"
            f"실제: {actual_schema}"
        )
    finally:
        conn.close()


def test_init_sql_uses_if_not_exists():
    """init.sql의 모든 CREATE 문에 IF NOT EXISTS가 포함되어 있는지 확인합니다.

    이는 멱등성의 구조적 전제 조건입니다.

    **Validates: Requirements 6.6**
    """
    sql = load_init_sql()

    # CREATE TABLE 문에 IF NOT EXISTS 포함 여부
    create_table_stmts = re.findall(
        r"CREATE\s+TABLE\s+.*?;", sql, re.IGNORECASE | re.DOTALL
    )
    for stmt in create_table_stmts:
        assert "IF NOT EXISTS" in stmt.upper(), (
            f"CREATE TABLE 문에 IF NOT EXISTS가 없음: {stmt[:80]}..."
        )

    # CREATE INDEX 문에 IF NOT EXISTS 포함 여부
    create_index_stmts = re.findall(
        r"CREATE\s+INDEX\s+.*?;", sql, re.IGNORECASE | re.DOTALL
    )
    for stmt in create_index_stmts:
        assert "IF NOT EXISTS" in stmt.upper(), (
            f"CREATE INDEX 문에 IF NOT EXISTS가 없음: {stmt[:80]}..."
        )


def test_expected_tables_exist():
    """init.sql 실행 후 예상 테이블과 인덱스가 모두 존재하는지 확인합니다.

    **Validates: Requirements 6.6**
    """
    conn = sqlite3.connect(":memory:")
    try:
        execute_init_schema(conn)
        schema = get_schema_info(conn)

        # 테이블 존재 확인
        assert "conversations" in schema["tables"], "conversations 테이블이 없습니다"
        assert "document_metadata" in schema["tables"], (
            "document_metadata 테이블이 없습니다"
        )

        # 인덱스 존재 확인
        assert "idx_conversations_session_id" in schema["indexes"]
        assert "idx_conversations_created_at" in schema["indexes"]
        assert "idx_document_metadata_doc_type" in schema["indexes"]
    finally:
        conn.close()
