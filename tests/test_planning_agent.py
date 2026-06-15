"""Planning Agent 단위 테스트.

sub_command 라우팅, 입력 검증, LLM 호출 에러 처리를 검증합니다.

Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.tool_agents.planning_agent.tool import PlanningTool


@pytest.fixture
def tool():
    """PlanningTool 인스턴스를 생성합니다."""
    return PlanningTool()


# ---------------------------------------------------------------------------
# Sub_command validation
# ---------------------------------------------------------------------------


class TestSubCommandValidation:
    """sub_command 검증 테스트."""

    @pytest.mark.asyncio
    async def test_unknown_sub_command_returns_error(self, tool: PlanningTool):
        """알 수 없는 sub_command는 에러 아티팩트를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="unknown")
        assert artifact["type"] == "planning"
        assert "error_message" in artifact
        assert "unknown" in artifact["error_message"]

    @pytest.mark.asyncio
    async def test_unknown_sub_command_includes_valid_list(self, tool: PlanningTool):
        """에러 아티팩트에 유효한 sub_command 목록이 포함되어야 합니다."""
        _, artifact = await tool._arun(sub_command="bad_cmd")
        assert "valid_commands" in artifact
        valid = artifact["valid_commands"]
        assert "breakdown_task" in valid
        assert "plan_schedule" in valid


# ---------------------------------------------------------------------------
# Input validation - empty task descriptions
# ---------------------------------------------------------------------------


class TestInputValidation:
    """입력 검증 테스트. Requirements: 5.4"""

    @pytest.mark.asyncio
    async def test_breakdown_task_missing_project(self, tool: PlanningTool):
        """breakdown_task에서 project가 비어있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="breakdown_task", project="", goal="test goal")
        assert "error_message" in artifact
        assert "project" in str(artifact.get("missing_fields", []))

    @pytest.mark.asyncio
    async def test_breakdown_task_missing_goal(self, tool: PlanningTool):
        """breakdown_task에서 goal이 비어있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="breakdown_task", project="test project", goal="")
        assert "error_message" in artifact
        assert "goal" in str(artifact.get("missing_fields", []))

    @pytest.mark.asyncio
    async def test_breakdown_task_both_missing(self, tool: PlanningTool):
        """breakdown_task에서 project와 goal 모두 비어있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="breakdown_task", project="", goal="")
        assert "error_message" in artifact
        missing = artifact.get("missing_fields", [])
        assert "project" in missing
        assert "goal" in missing

    @pytest.mark.asyncio
    async def test_breakdown_task_whitespace_only_project(self, tool: PlanningTool):
        """breakdown_task에서 project가 공백만 있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="breakdown_task", project="   ", goal="test")
        assert "error_message" in artifact

    @pytest.mark.asyncio
    async def test_plan_schedule_missing_tasks(self, tool: PlanningTool):
        """plan_schedule에서 tasks가 비어있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="plan_schedule", tasks="")
        assert "error_message" in artifact
        assert "tasks" in str(artifact.get("missing_fields", []))

    @pytest.mark.asyncio
    async def test_plan_schedule_whitespace_only_tasks(self, tool: PlanningTool):
        """plan_schedule에서 tasks가 공백만 있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="plan_schedule", tasks="   ")
        assert "error_message" in artifact


# ---------------------------------------------------------------------------
# Sub_command routing with mocked LLM
# ---------------------------------------------------------------------------


class TestBreakdownTaskSubCommand:
    """breakdown_task sub_command 테스트 (LLM mocked)."""

    @pytest.mark.asyncio
    async def test_breakdown_task_returns_tasks_array(self, tool: PlanningTool):
        """breakdown_task는 tasks 배열을 포함하는 artifact를 반환해야 합니다."""
        mock_response = json.dumps({
            "project_name": "웹 앱 개발",
            "tasks": [
                {
                    "task_name": "DB 설계",
                    "description": "데이터 모델 설계",
                    "estimated_hours": 8,
                    "priority": "high",
                    "dependencies": [],
                },
                {
                    "task_name": "API 개발",
                    "description": "REST API 구현",
                    "estimated_hours": 16,
                    "priority": "high",
                    "dependencies": ["DB 설계"],
                },
            ],
            "dependencies": [["DB 설계", "API 개발"]],
            "total_estimated_hours": 24,
        })

        with patch("app.tool_agents.planning_agent.tool.call_llm", new_callable=AsyncMock, return_value=mock_response):
            _, artifact = await tool._arun(
                sub_command="breakdown_task", project="웹 앱", goal="MVP 출시"
            )

        assert artifact["type"] == "planning"
        assert artifact["sub_command"] == "breakdown_task"
        assert "tasks" in artifact
        assert isinstance(artifact["tasks"], list)
        assert len(artifact["tasks"]) == 2
        assert artifact["total_estimated_hours"] == 24
        assert "dependencies" in artifact

    @pytest.mark.asyncio
    async def test_breakdown_task_json_parse_failure(self, tool: PlanningTool):
        """JSON 파싱 실패 시 raw text를 content로 반환해야 합니다. Requirements: 5.6"""
        raw_text = "프로젝트를 3단계로 나누세요..."

        with patch("app.tool_agents.planning_agent.tool.call_llm", new_callable=AsyncMock, return_value=raw_text):
            _, artifact = await tool._arun(
                sub_command="breakdown_task", project="test", goal="test"
            )

        assert artifact["type"] == "planning"
        assert artifact.get("content") == raw_text


class TestPlanScheduleSubCommand:
    """plan_schedule sub_command 테스트 (LLM mocked)."""

    @pytest.mark.asyncio
    async def test_plan_schedule_returns_timeline(self, tool: PlanningTool):
        """plan_schedule은 schedule 배열을 포함하는 artifact를 반환해야 합니다."""
        mock_response = json.dumps({
            "tasks": [
                {"name": "코드리뷰", "estimated_hours": 2, "deadline": "2024-03-15", "priority": "high"},
            ],
            "schedule": [
                {"date": "2024-03-14", "tasks": ["코드리뷰"]},
            ],
            "priorities": ["high: 코드리뷰"],
        })

        with patch("app.tool_agents.planning_agent.tool.call_llm", new_callable=AsyncMock, return_value=mock_response):
            _, artifact = await tool._arun(
                sub_command="plan_schedule",
                tasks="코드리뷰 - 2시간 - 마감 3/15",
                start_date="2024-03-14",
            )

        assert artifact["type"] == "planning"
        assert artifact["sub_command"] == "plan_schedule"
        assert "tasks" in artifact
        assert "schedule" in artifact
        assert "priorities" in artifact
        assert isinstance(artifact["schedule"], list)

    @pytest.mark.asyncio
    async def test_plan_schedule_json_parse_failure(self, tool: PlanningTool):
        """JSON 파싱 실패 시 raw text를 content로 반환해야 합니다."""
        raw_text = "다음과 같이 일정을 계획해보세요..."

        with patch("app.tool_agents.planning_agent.tool.call_llm", new_callable=AsyncMock, return_value=raw_text):
            _, artifact = await tool._arun(
                sub_command="plan_schedule", tasks="task1, task2"
            )

        assert artifact["type"] == "planning"
        assert artifact.get("content") == raw_text


# ---------------------------------------------------------------------------
# LLM failure handling
# ---------------------------------------------------------------------------


class TestLLMFailure:
    """LLM 호출 실패 시 에러 처리. Requirements: 5.5"""

    @pytest.mark.asyncio
    async def test_breakdown_task_llm_failure(self, tool: PlanningTool):
        """breakdown_task에서 LLM 실패 시 에러 아티팩트를 반환해야 합니다."""
        with patch("app.tool_agents.planning_agent.tool.call_llm", new_callable=AsyncMock, side_effect=RuntimeError("API error")):
            _, artifact = await tool._arun(
                sub_command="breakdown_task", project="test", goal="test"
            )

        assert artifact["type"] == "planning"
        assert "error_message" in artifact
        assert "API error" in artifact["error_message"]
        assert artifact.get("sub_command") == "breakdown_task"

    @pytest.mark.asyncio
    async def test_plan_schedule_llm_failure(self, tool: PlanningTool):
        """plan_schedule에서 LLM 실패 시 에러 아티팩트를 반환해야 합니다."""
        with patch("app.tool_agents.planning_agent.tool.call_llm", new_callable=AsyncMock, side_effect=RuntimeError("timeout")):
            _, artifact = await tool._arun(
                sub_command="plan_schedule", tasks="task1"
            )

        assert "error_message" in artifact
        assert artifact.get("sub_command") == "plan_schedule"


# ---------------------------------------------------------------------------
# Factory and deprecated flags
# ---------------------------------------------------------------------------


class TestDeprecatedFlags:
    """기존 팩토리들의 deprecated 플래그 테스트."""

    def test_planning_factory_not_deprecated(self):
        from app.tool_agents.planning_agent.factory import PlanningFactory

        factory = PlanningFactory()
        assert factory.deprecated is False
        assert factory.agent_type == "planning"
        assert factory.category == "Planning"

    def test_task_breakdown_factory_deprecated(self):
        from app.tool_agents.task_breakdown_agent.factory import TaskBreakdownFactory

        factory = TaskBreakdownFactory()
        assert factory.deprecated is True

    def test_schedule_planner_factory_deprecated(self):
        from app.tool_agents.schedule_planner_agent.factory import SchedulePlannerFactory

        factory = SchedulePlannerFactory()
        assert factory.deprecated is True


class TestPlanningFactory:
    """PlanningFactory 생성 테스트."""

    def test_factory_creates_tool(self):
        from app.tool_agents.planning_agent.factory import PlanningFactory

        factory = PlanningFactory()
        tool = factory.create_tool({})
        assert tool.name == "planning"
        assert isinstance(tool, PlanningTool)
