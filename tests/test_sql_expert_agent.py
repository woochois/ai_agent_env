"""SQL Expert Agent 단위 테스트.

sub_command 라우팅, 입력 검증, 에러 처리를 검증합니다.

Property 1: Expert Agent Sub_Command 라우팅 및 입력 검증
Property 2: SQL Expert 서브커맨드 아티팩트 구조 정합성
Property 3: EXPLAIN ANALYZE는 SELECT 전용

Validates: Requirements 1.2, 1.3, 1.5, 1.7, 1.8, 1.9, 1.12
"""

from __future__ import annotations

import pytest

from app.tool_agents.sql_expert_agent.tool import SqlExpertTool


@pytest.fixture
def tool():
    """SqlExpertTool 인스턴스를 생성합니다."""
    return SqlExpertTool()


# ---------------------------------------------------------------------------
# Sub_command routing - valid commands (synchronous: format, lint)
# ---------------------------------------------------------------------------


class TestFormatSubCommand:
    """format sub_command 테스트."""

    def test_format_returns_formatted_sql_and_artifact(self, tool: SqlExpertTool):
        """format은 formatted_sql과 original을 포함하는 artifact를 반환해야 합니다."""
        content, artifact = tool._run(sub_command="format", sql="select id from users where id = 1")

        assert artifact["type"] == "sql_expert"
        assert artifact["sub_command"] == "format"
        assert "formatted_sql" in artifact
        assert "original" in artifact
        assert artifact["original"] == "select id from users where id = 1"
        # formatted_sql은 키워드가 대문자화됨
        assert "SELECT" in artifact["formatted_sql"]
        assert "FROM" in artifact["formatted_sql"]

    def test_format_uppercases_keywords(self, tool: SqlExpertTool):
        """format은 SQL 키워드를 대문자화해야 합니다."""
        _, artifact = tool._run(sub_command="format", sql="select a, b from t where x = 1")
        formatted = artifact["formatted_sql"]
        assert "SELECT" in formatted
        assert "FROM" in formatted
        assert "WHERE" in formatted

    def test_format_adds_line_breaks(self, tool: SqlExpertTool):
        """format은 주요 절 앞에 줄바꿈을 추가해야 합니다."""
        _, artifact = tool._run(sub_command="format", sql="select id from users order by name")
        formatted = artifact["formatted_sql"]
        assert "\nFROM" in formatted
        assert "\nORDER BY" in formatted

    def test_format_empty_sql_returns_error(self, tool: SqlExpertTool):
        """sql이 비어있으면 에러 아티팩트를 반환해야 합니다."""
        _, artifact = tool._run(sub_command="format", sql="")
        assert artifact["type"] == "sql_expert"
        assert "error_message" in artifact
        assert "sql" in artifact["error_message"].lower() or "sql" in artifact.get("missing_field", "")

    def test_format_whitespace_only_sql_returns_error(self, tool: SqlExpertTool):
        """공백만 있는 sql은 에러 아티팩트를 반환해야 합니다."""
        _, artifact = tool._run(sub_command="format", sql="   ")
        assert "error_message" in artifact


class TestLintSubCommand:
    """lint sub_command 테스트."""

    def test_lint_returns_issues_list(self, tool: SqlExpertTool):
        """lint는 issues 리스트를 포함하는 artifact를 반환해야 합니다."""
        _, artifact = tool._run(sub_command="lint", sql="SELECT * FROM users")

        assert artifact["type"] == "sql_expert"
        assert artifact["sub_command"] == "lint"
        assert "issues" in artifact
        assert isinstance(artifact["issues"], list)

    def test_lint_issues_have_required_fields(self, tool: SqlExpertTool):
        """각 issue는 rule, severity, message, suggestion 필드를 포함해야 합니다."""
        _, artifact = tool._run(sub_command="lint", sql="SELECT * FROM users")
        issues = artifact["issues"]
        assert len(issues) > 0
        for issue in issues:
            assert "rule" in issue
            assert "severity" in issue
            assert issue["severity"] in ("error", "warning")
            assert "message" in issue
            assert "suggestion" in issue

    def test_lint_detects_select_star(self, tool: SqlExpertTool):
        """lint는 SELECT * 패턴을 감지해야 합니다."""
        _, artifact = tool._run(sub_command="lint", sql="SELECT * FROM users")
        assert any(i["rule"] == "select_star" for i in artifact["issues"])

    def test_lint_detects_delete_without_where(self, tool: SqlExpertTool):
        """lint는 WHERE 없는 DELETE를 감지해야 합니다."""
        _, artifact = tool._run(sub_command="lint", sql="DELETE FROM users")
        issues = artifact["issues"]
        assert any(i["rule"] == "delete_without_where" for i in issues)
        assert any(i["severity"] == "error" for i in issues if i["rule"] == "delete_without_where")

    def test_lint_empty_sql_returns_error(self, tool: SqlExpertTool):
        """sql이 비어있으면 에러 아티팩트를 반환해야 합니다."""
        _, artifact = tool._run(sub_command="lint", sql="")
        assert "error_message" in artifact


# ---------------------------------------------------------------------------
# Sub_command validation - invalid sub_commands
# ---------------------------------------------------------------------------


class TestInvalidSubCommand:
    """유효하지 않은 sub_command 테스트."""

    def test_unknown_sub_command_returns_error_artifact(self, tool: SqlExpertTool):
        """알 수 없는 sub_command는 에러 아티팩트를 반환해야 합니다."""
        _, artifact = tool._run(sub_command="unknown_command")
        assert artifact["type"] == "sql_expert"
        assert "error_message" in artifact
        assert "unknown_command" in artifact["error_message"]

    def test_unknown_sub_command_includes_valid_list(self, tool: SqlExpertTool):
        """에러 아티팩트에 유효한 sub_command 목록이 포함되어야 합니다."""
        _, artifact = tool._run(sub_command="bad")
        assert "valid_sub_commands" in artifact
        valid = artifact["valid_sub_commands"]
        assert "format" in valid
        assert "lint" in valid
        assert "explain" in valid
        assert "analyze_slow_query" in valid

    def test_unknown_sub_command_includes_requested_value(self, tool: SqlExpertTool):
        """에러 아티팩트에 요청된 sub_command 값이 포함되어야 합니다."""
        _, artifact = tool._run(sub_command="foobar")
        assert artifact.get("requested_sub_command") == "foobar"

    def test_empty_sub_command_returns_error(self, tool: SqlExpertTool):
        """빈 문자열 sub_command는 에러를 반환해야 합니다."""
        _, artifact = tool._run(sub_command="")
        assert "error_message" in artifact
        assert "valid_sub_commands" in artifact


# ---------------------------------------------------------------------------
# Async sub_commands (explain, analyze_slow_query)
# ---------------------------------------------------------------------------


class TestExplainSubCommand:
    """explain sub_command 테스트 (DB 미연결 시나리오)."""

    @pytest.mark.asyncio
    async def test_explain_empty_query_returns_error(self, tool: SqlExpertTool):
        """query가 비어있으면 에러 아티팩트를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="explain", query="")
        assert "error_message" in artifact
        assert "query" in artifact["error_message"].lower() or "query" in artifact.get("missing_field", "")

    @pytest.mark.asyncio
    async def test_explain_no_db_returns_unavailable(self, tool: SqlExpertTool):
        """DB 연결이 없으면 database_unavailable 에러를 반환해야 합니다."""
        # db_provider가 None인 상태
        _, artifact = await tool._arun(sub_command="explain", query="SELECT 1")
        assert artifact["type"] == "sql_expert"
        assert artifact.get("note") == "database_unavailable"

    @pytest.mark.asyncio
    async def test_explain_analyze_non_select_returns_error(self):
        """ANALYZE=True + 비-SELECT 쿼리는 에러를 반환해야 합니다.

        Property 3: EXPLAIN ANALYZE는 SELECT 전용
        """
        # db_provider가 엔진을 반환하도록 mock
        class FakeEngine:
            pass

        class FakeDB:
            engine = FakeEngine()

        tool = SqlExpertTool(db_provider=lambda: FakeDB())
        _, artifact = await tool._arun(
            sub_command="explain", query="UPDATE users SET x = 1", analyze=True
        )
        assert "error_message" in artifact
        assert "ANALYZE" in artifact["error_message"]
        assert "SELECT" in artifact["error_message"]

    @pytest.mark.asyncio
    async def test_explain_analyze_select_allowed(self):
        """ANALYZE=True + SELECT 쿼리는 에러가 아닌 정상 진행이어야 합니다 (DB 연결 시)."""
        # 이 테스트는 DB가 없으므로 db_provider가 None → database_unavailable
        tool = SqlExpertTool()
        _, artifact = await tool._arun(
            sub_command="explain", query="SELECT 1 FROM users", analyze=True
        )
        # DB 없으므로 database_unavailable이지만, ANALYZE SELECT 에러는 아님
        assert artifact.get("note") == "database_unavailable"
        # "ANALYZE는 SELECT 쿼리에만" 에러 메시지가 아님을 확인
        assert "ANALYZE" not in artifact.get("error_message", "") or "SELECT" not in artifact.get("error_message", "")


class TestAnalyzeSlowQuerySubCommand:
    """analyze_slow_query sub_command 테스트."""

    @pytest.mark.asyncio
    async def test_analyze_slow_query_no_db_returns_unavailable(self, tool: SqlExpertTool):
        """DB 연결이 없으면 database_unavailable 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="analyze_slow_query")
        assert artifact["type"] == "sql_expert"
        assert artifact.get("note") == "database_unavailable"


# ---------------------------------------------------------------------------
# Factory deprecated flags
# ---------------------------------------------------------------------------


class TestDeprecatedFlags:
    """기존 팩토리들의 deprecated 플래그 테스트. Requirements: 1.12"""

    def test_sql_expert_factory_not_deprecated(self):
        from app.tool_agents.sql_expert_agent.factory import SqlExpertFactory

        factory = SqlExpertFactory()
        assert factory.deprecated is False

    def test_sql_formatter_factory_deprecated(self):
        from app.tool_agents.sql_formatter_agent.factory import SqlFormatterFactory

        factory = SqlFormatterFactory()
        assert factory.deprecated is True

    def test_sql_lint_factory_deprecated(self):
        from app.tool_agents.sql_lint_agent.factory import SqlLintFactory

        factory = SqlLintFactory()
        assert factory.deprecated is True

    def test_query_explain_factory_deprecated(self):
        from app.tool_agents.query_explain_agent.factory import QueryExplainFactory

        factory = QueryExplainFactory()
        assert factory.deprecated is True

    def test_slow_query_analyzer_factory_deprecated(self):
        from app.tool_agents.slow_query_analyzer_agent.factory import SlowQueryAnalyzerFactory

        factory = SlowQueryAnalyzerFactory()
        assert factory.deprecated is True


# ---------------------------------------------------------------------------
# Factory creation
# ---------------------------------------------------------------------------


class TestSqlExpertFactory:
    """SqlExpertFactory 생성 테스트."""

    def test_factory_creates_tool(self):
        from app.tool_agents.sql_expert_agent.factory import SqlExpertFactory

        factory = SqlExpertFactory()
        tool = factory.create_tool({})
        assert tool.name == "sql_expert"
        assert isinstance(tool, SqlExpertTool)

    def test_factory_agent_type(self):
        from app.tool_agents.sql_expert_agent.factory import SqlExpertFactory

        factory = SqlExpertFactory()
        assert factory.agent_type == "sql_expert"
        assert factory.category == "SQL"
