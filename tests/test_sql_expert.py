"""SQL Expert Agent 단위 테스트.

sub_command 라우팅, 입력 검증, 에러 처리를 검증합니다.
"""

from __future__ import annotations

import pytest

from app.tool_agents.sql_expert_agent.tool import (
    AGENT_TYPE,
    SqlExpertInput,
    SqlExpertTool,
    _VALID_COMMANDS,
)
from app.tool_agents.sql_expert_agent.factory import SqlExpertFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tool():
    """DB 미연결 상태의 SqlExpertTool 인스턴스."""
    return SqlExpertTool(
        name="sql_expert",
        description="test",
        db_provider=lambda: None,
    )


# ---------------------------------------------------------------------------
# Sub_command routing tests
# ---------------------------------------------------------------------------


class TestSubCommandRouting:
    """sub_command에 따라 올바른 핸들러가 호출되는지 검증."""

    @pytest.mark.asyncio
    async def test_format_routes_correctly(self, tool):
        """format sub_command는 포맷된 SQL을 반환한다."""
        content, artifact = await tool._arun(
            sub_command="format", sql="select id from users"
        )
        assert artifact["type"] == AGENT_TYPE
        assert "formatted_sql" in artifact
        assert artifact["original"] == "select id from users"
        # 키워드가 대문자화되어야 함
        assert "SELECT" in artifact["formatted_sql"]

    @pytest.mark.asyncio
    async def test_lint_routes_correctly(self, tool):
        """lint sub_command는 issues 리스트를 반환한다."""
        content, artifact = await tool._arun(
            sub_command="lint", sql="SELECT * FROM users"
        )
        assert artifact["type"] == AGENT_TYPE
        assert "issues" in artifact
        assert isinstance(artifact["issues"], list)
        # SELECT * 경고가 있어야 함
        rules = [issue["rule"] for issue in artifact["issues"]]
        assert "select_star" in rules

    @pytest.mark.asyncio
    async def test_lint_issue_fields(self, tool):
        """lint 결과의 각 issue가 필수 필드를 포함한다."""
        _, artifact = await tool._arun(
            sub_command="lint", sql="DELETE FROM users"
        )
        for issue in artifact["issues"]:
            assert "rule" in issue
            assert "severity" in issue
            assert issue["severity"] in ("error", "warning")
            assert "message" in issue
            assert "suggestion" in issue

    @pytest.mark.asyncio
    async def test_explain_requires_db(self, tool):
        """explain sub_command는 DB 미연결 시 database_unavailable 에러를 반환한다."""
        _, artifact = await tool._arun(
            sub_command="explain", query="SELECT 1"
        )
        assert artifact["type"] == AGENT_TYPE
        assert artifact.get("note") == "database_unavailable"

    @pytest.mark.asyncio
    async def test_analyze_slow_query_requires_db(self, tool):
        """analyze_slow_query sub_command는 DB 미연결 시 database_unavailable 에러를 반환한다."""
        _, artifact = await tool._arun(
            sub_command="analyze_slow_query", limit=5
        )
        assert artifact["type"] == AGENT_TYPE
        assert artifact.get("note") == "database_unavailable"


# ---------------------------------------------------------------------------
# Invalid sub_command tests
# ---------------------------------------------------------------------------


class TestInvalidSubCommand:
    """유효하지 않은 sub_command에 대한 에러 처리를 검증."""

    @pytest.mark.asyncio
    async def test_unknown_sub_command_returns_error(self, tool):
        """알 수 없는 sub_command는 에러 아티팩트를 반환한다."""
        _, artifact = await tool._arun(sub_command="unknown_cmd", sql="SELECT 1")
        assert artifact["type"] == AGENT_TYPE
        assert "error_message" in artifact
        assert "unknown_cmd" in artifact["error_message"]
        assert "valid_commands" in artifact
        assert sorted(_VALID_COMMANDS) == artifact["valid_commands"]

    @pytest.mark.asyncio
    async def test_empty_sub_command_returns_error(self, tool):
        """빈 sub_command는 에러 아티팩트를 반환한다."""
        _, artifact = await tool._arun(sub_command="", sql="SELECT 1")
        assert artifact["type"] == AGENT_TYPE
        assert "error_message" in artifact
        assert "valid_commands" in artifact

    @pytest.mark.asyncio
    async def test_error_artifact_includes_requested_value(self, tool):
        """에러 아티팩트에 요청된 sub_command 값이 포함된다."""
        _, artifact = await tool._arun(sub_command="foobar")
        assert artifact["sub_command"] == "foobar"


# ---------------------------------------------------------------------------
# Input validation tests
# ---------------------------------------------------------------------------


class TestInputValidation:
    """필수 입력 필드 검증을 확인."""

    @pytest.mark.asyncio
    async def test_format_empty_sql_returns_error(self, tool):
        """format에서 sql이 비어있으면 에러를 반환한다."""
        _, artifact = await tool._arun(sub_command="format", sql="")
        assert "error_message" in artifact
        assert "sql" in artifact["error_message"] or "sql" in artifact.get("missing_field", "")

    @pytest.mark.asyncio
    async def test_lint_empty_sql_returns_error(self, tool):
        """lint에서 sql이 비어있으면 에러를 반환한다."""
        _, artifact = await tool._arun(sub_command="lint", sql="")
        assert "error_message" in artifact
        assert "sql" in artifact["error_message"] or "sql" in artifact.get("missing_field", "")

    @pytest.mark.asyncio
    async def test_explain_empty_query_returns_error(self, tool):
        """explain에서 query가 비어있으면 에러를 반환한다."""
        _, artifact = await tool._arun(sub_command="explain", query="")
        assert "error_message" in artifact
        assert "query" in artifact["error_message"] or "query" in artifact.get("missing_field", "")

    @pytest.mark.asyncio
    async def test_explain_analyze_non_select_returns_error(self, tool):
        """explain에서 analyze=True이고 비-SELECT 쿼리이면 에러를 반환한다."""
        _, artifact = await tool._arun(
            sub_command="explain", query="UPDATE users SET name='x'", analyze=True
        )
        assert "error_message" in artifact
        assert "SELECT" in artifact["error_message"]

    @pytest.mark.asyncio
    async def test_format_whitespace_only_sql_returns_error(self, tool):
        """format에서 공백만 있는 sql도 에러를 반환한다."""
        _, artifact = await tool._arun(sub_command="format", sql="   ")
        assert "error_message" in artifact


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


class TestSqlExpertFactory:
    """SqlExpertFactory 메타데이터와 동작 검증."""

    def test_factory_agent_type(self):
        factory = SqlExpertFactory()
        assert factory.agent_type == "sql_expert"

    def test_factory_not_deprecated(self):
        factory = SqlExpertFactory()
        assert factory.deprecated is False

    def test_factory_category(self):
        factory = SqlExpertFactory()
        assert factory.category == "SQL"

    def test_factory_creates_tool(self):
        factory = SqlExpertFactory(db_provider=lambda: None)
        tool = factory.create_tool({"name": "sql_expert", "description": "test"})
        assert isinstance(tool, SqlExpertTool)
        assert tool.name == "sql_expert"


# ---------------------------------------------------------------------------
# Original factories deprecated check
# ---------------------------------------------------------------------------


class TestOriginalFactoriesDeprecated:
    """기존 개별 에이전트 팩토리들의 deprecated 플래그를 확인."""

    def test_sql_formatter_deprecated(self):
        from app.tool_agents.sql_formatter_agent.factory import SqlFormatterFactory

        assert SqlFormatterFactory.deprecated is True

    def test_sql_lint_deprecated(self):
        from app.tool_agents.sql_lint_agent.factory import SqlLintFactory

        assert SqlLintFactory.deprecated is True

    def test_query_explain_deprecated(self):
        from app.tool_agents.query_explain_agent.factory import QueryExplainFactory

        assert QueryExplainFactory.deprecated is True

    def test_slow_query_analyzer_deprecated(self):
        from app.tool_agents.slow_query_analyzer_agent.factory import SlowQueryAnalyzerFactory

        assert SlowQueryAnalyzerFactory.deprecated is True
