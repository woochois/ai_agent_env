"""Schema Expert Agent 단위 테스트.

sub_command 라우팅, 입력 검증, DB 불가 시 에러 처리를 검증합니다.

Validates: Requirements 2.1, 2.2, 2.5, 2.7, 2.8, 2.9, 2.10
"""

from __future__ import annotations

import pytest

from app.tool_agents.schema_expert_agent.tool import SchemaExpertTool


@pytest.fixture
def tool():
    """SchemaExpertTool 인스턴스를 생성합니다 (DB 없음)."""
    return SchemaExpertTool()


# ---------------------------------------------------------------------------
# Sub_command routing - valid commands
# ---------------------------------------------------------------------------


class TestGenerateDdlSubCommand:
    """generate_ddl sub_command 테스트."""

    @pytest.mark.asyncio
    async def test_generate_ddl_basic(self, tool: SchemaExpertTool):
        """generate_ddl은 DDL을 포함하는 artifact를 반환해야 합니다."""
        columns = [
            {"name": "id", "type": "SERIAL", "nullable": False, "primary_key": True, "unique": False},
            {"name": "name", "type": "VARCHAR(255)", "nullable": False, "primary_key": False, "unique": True},
        ]
        content, artifact = await tool._arun(
            sub_command="generate_ddl",
            table_name="users",
            columns=columns,
        )

        assert artifact["type"] == "schema_expert"
        assert artifact["sub_command"] == "generate_ddl"
        assert "create_table" in artifact
        assert "CREATE TABLE" in artifact["create_table"]
        assert "users" in artifact["create_table"]
        assert "PRIMARY KEY" in artifact["create_table"]

    @pytest.mark.asyncio
    async def test_generate_ddl_includes_indexes_for_unique(self, tool: SchemaExpertTool):
        """UNIQUE 컬럼에 대한 CREATE INDEX가 포함되어야 합니다."""
        columns = [
            {"name": "id", "type": "SERIAL", "nullable": False, "primary_key": True, "unique": False},
            {"name": "email", "type": "VARCHAR(255)", "nullable": False, "primary_key": False, "unique": True},
        ]
        _, artifact = await tool._arun(
            sub_command="generate_ddl",
            table_name="accounts",
            columns=columns,
        )

        assert "indexes" in artifact
        assert len(artifact["indexes"]) > 0
        assert "CREATE" in artifact["indexes"][0]
        assert "email" in artifact["indexes"][0]

    @pytest.mark.asyncio
    async def test_generate_ddl_missing_table_name(self, tool: SchemaExpertTool):
        """table_name이 비어있으면 에러 아티팩트를 반환해야 합니다."""
        _, artifact = await tool._arun(
            sub_command="generate_ddl",
            table_name="",
            columns=[{"name": "id", "type": "INTEGER"}],
        )
        assert "error_message" in artifact
        assert "table_name" in str(artifact.get("missing_fields", []))

    @pytest.mark.asyncio
    async def test_generate_ddl_missing_columns(self, tool: SchemaExpertTool):
        """columns가 비어있으면 에러 아티팩트를 반환해야 합니다."""
        _, artifact = await tool._arun(
            sub_command="generate_ddl",
            table_name="test_table",
            columns=[],
        )
        assert "error_message" in artifact
        assert "columns" in str(artifact.get("missing_fields", []))


class TestAdviseIndexSubCommand:
    """advise_index sub_command 테스트."""

    @pytest.mark.asyncio
    async def test_advise_index_returns_recommendations(self, tool: SchemaExpertTool):
        """advise_index는 recommendations 리스트를 반환해야 합니다."""
        _, artifact = await tool._arun(
            sub_command="advise_index",
            query="SELECT * FROM orders WHERE customer_id = 123 ORDER BY created_at",
        )
        assert artifact["type"] == "schema_expert"
        assert artifact["sub_command"] == "advise_index"
        assert "recommendations" in artifact
        assert isinstance(artifact["recommendations"], list)
        assert len(artifact["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_advise_index_recommendation_structure(self, tool: SchemaExpertTool):
        """각 recommendation은 columns, rationale, ddl 필드를 포함해야 합니다."""
        _, artifact = await tool._arun(
            sub_command="advise_index",
            query="SELECT id FROM users WHERE status = 'active' AND age > 18",
        )
        for rec in artifact["recommendations"]:
            assert "columns" in rec
            assert "rationale" in rec
            assert "ddl" in rec

    @pytest.mark.asyncio
    async def test_advise_index_extracts_predicate_columns(self, tool: SchemaExpertTool):
        """WHERE/JOIN/ORDER BY 컬럼이 recommendations에 반영되어야 합니다."""
        _, artifact = await tool._arun(
            sub_command="advise_index",
            query="SELECT * FROM orders JOIN users ON orders.user_id = users.id WHERE orders.status = 'pending'",
        )
        all_columns = []
        for rec in artifact["recommendations"]:
            all_columns.extend(rec["columns"])
        # status는 WHERE에서 추출되어야 함
        assert "status" in all_columns

    @pytest.mark.asyncio
    async def test_advise_index_empty_query_returns_error(self, tool: SchemaExpertTool):
        """query가 비어있으면 에러 아티팩트를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="advise_index", query="")
        assert "error_message" in artifact


# ---------------------------------------------------------------------------
# Database unavailability handling
# ---------------------------------------------------------------------------


class TestDatabaseUnavailability:
    """DB 연결 불가 시 에러 처리 테스트."""

    @pytest.mark.asyncio
    async def test_inspect_schema_no_db(self, tool: SchemaExpertTool):
        """DB가 없을 때 inspect_schema는 database_unavailable을 반환해야 합니다."""
        _, artifact = await tool._arun(
            sub_command="inspect_schema",
            table="users",
        )
        assert artifact["type"] == "schema_expert"
        assert artifact.get("note") == "database_unavailable"

    @pytest.mark.asyncio
    async def test_generate_er_diagram_no_db(self, tool: SchemaExpertTool):
        """DB가 없을 때 generate_er_diagram은 database_unavailable을 반환해야 합니다."""
        _, artifact = await tool._arun(
            sub_command="generate_er_diagram",
            schema_name="public",
        )
        assert artifact["type"] == "schema_expert"
        assert artifact.get("note") == "database_unavailable"

    @pytest.mark.asyncio
    async def test_advise_index_no_db_still_returns_recommendations(self, tool: SchemaExpertTool):
        """DB가 없어도 advise_index는 휴리스틱 추천을 반환해야 합니다."""
        _, artifact = await tool._arun(
            sub_command="advise_index",
            query="SELECT * FROM users WHERE id = 1",
        )
        # advise_index는 DB 없이도 휴리스틱으로 동작
        assert artifact["type"] == "schema_expert"
        assert "recommendations" in artifact
        assert artifact.get("seq_scan_detected") is None  # DB 미연결이므로 None


# ---------------------------------------------------------------------------
# Sub_command validation - invalid sub_commands
# ---------------------------------------------------------------------------


class TestInvalidSubCommand:
    """유효하지 않은 sub_command 테스트."""

    @pytest.mark.asyncio
    async def test_unknown_sub_command_returns_error(self, tool: SchemaExpertTool):
        """알 수 없는 sub_command는 에러 아티팩트를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="unknown")
        assert artifact["type"] == "schema_expert"
        assert "error_message" in artifact
        assert "unknown" in artifact["error_message"]

    @pytest.mark.asyncio
    async def test_unknown_sub_command_includes_valid_list(self, tool: SchemaExpertTool):
        """에러 아티팩트에 유효한 sub_command 목록이 포함되어야 합니다."""
        _, artifact = await tool._arun(sub_command="bad_cmd")
        assert "valid_commands" in artifact
        valid = artifact["valid_commands"]
        assert "generate_ddl" in valid
        assert "inspect_schema" in valid
        assert "generate_er_diagram" in valid
        assert "advise_index" in valid


# ---------------------------------------------------------------------------
# Factory and deprecated flags
# ---------------------------------------------------------------------------


class TestDeprecatedFlags:
    """기존 팩토리들의 deprecated 플래그 테스트. Requirements: 2.10"""

    def test_schema_expert_factory_not_deprecated(self):
        from app.tool_agents.schema_expert_agent.factory import SchemaExpertFactory

        factory = SchemaExpertFactory()
        assert factory.deprecated is False
        assert factory.agent_type == "schema_expert"
        assert factory.category == "Schema"

    def test_ddl_generator_factory_deprecated(self):
        from app.tool_agents.ddl_generator_agent.factory import DDLGeneratorFactory

        factory = DDLGeneratorFactory()
        assert factory.deprecated is True

    def test_schema_inspector_factory_deprecated(self):
        from app.tool_agents.schema_inspector_agent.factory import SchemaInspectorFactory

        factory = SchemaInspectorFactory()
        assert factory.deprecated is True

    def test_er_diagram_factory_deprecated(self):
        from app.tool_agents.er_diagram_agent.factory import ERDiagramFactory

        factory = ERDiagramFactory()
        assert factory.deprecated is True

    def test_index_advisor_factory_deprecated(self):
        from app.tool_agents.index_advisor_agent.factory import IndexAdvisorFactory

        factory = IndexAdvisorFactory()
        assert factory.deprecated is True


class TestSchemaExpertFactory:
    """SchemaExpertFactory 생성 테스트."""

    def test_factory_creates_tool(self):
        from app.tool_agents.schema_expert_agent.factory import SchemaExpertFactory

        factory = SchemaExpertFactory()
        tool = factory.create_tool({})
        assert tool.name == "schema_expert"
        assert isinstance(tool, SchemaExpertTool)
