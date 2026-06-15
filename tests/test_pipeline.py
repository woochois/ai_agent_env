"""Pipeline 모듈 유닛 테스트.

테스트 대상:
- 성공적인 멀티 스텝 파이프라인 실행
- 스텝 실패 시 즉시 중단
- 검증 에러 (빈 steps, 초과 steps, 미등록 agent_type)
- input_mapping 해석
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.framework.pipeline import (
    ExecutionTrace,
    InputMappingError,
    PipelineDefinition,
    PipelineExecutor,
    PipelineStep,
    StepResult,
)
from app.framework.registry import ToolAgentRegistry
from app.framework.base import BaseAgentTool, BaseToolFactory


# ---------------------------------------------------------------------------
# Test Fixtures: Mock Tool Agent
# ---------------------------------------------------------------------------


class MockTool(BaseAgentTool):
    """테스트용 Mock Tool Agent."""

    name: str = "mock_agent"
    description: str = "Mock tool for testing"

    # 호출 시 반환할 artifact를 외부에서 주입
    _mock_artifact: dict[str, Any] = {}
    _should_fail: bool = False

    async def _arun(self, **kwargs: Any) -> tuple[str, dict]:
        if self._should_fail:
            return "", {"type": "mock_agent", "error_message": "Mock failure"}
        return "success", self._mock_artifact

    def _run(self, **kwargs: Any) -> tuple[str, dict]:
        raise NotImplementedError


class MockFactory(BaseToolFactory):
    """테스트용 Mock 팩토리."""

    agent_type: str = "mock_agent"

    def __init__(self, agent_type: str = "mock_agent", artifact: dict | None = None, should_fail: bool = False):
        self.agent_type = agent_type
        self._artifact = artifact or {"type": agent_type, "result": "ok"}
        self._should_fail = should_fail

    def create_tool(self, tool_config: dict[str, Any]) -> BaseAgentTool:
        tool = MockTool(name=self.agent_type, description="Mock")
        tool._mock_artifact = self._artifact
        tool._should_fail = self._should_fail
        return tool


def _create_registry_with(*factories: MockFactory) -> ToolAgentRegistry:
    """테스트용 팩토리를 등록한 레지스트리를 생성합니다."""
    reg = ToolAgentRegistry(package="nonexistent.package")
    for factory in factories:
        reg.register(factory)
    return reg


# ---------------------------------------------------------------------------
# Test: Validation
# ---------------------------------------------------------------------------


class TestPipelineValidation:
    """파이프라인 사전 검증 테스트."""

    @pytest.mark.asyncio
    async def test_empty_steps_validation_error(self):
        """빈 steps 배열 → 검증 에러."""
        registry = _create_registry_with(MockFactory("agent_a"))
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(steps=[])

        errors = await executor.validate(definition)

        assert len(errors) == 1
        assert "at least 1 step" in errors[0]

    @pytest.mark.asyncio
    async def test_exceed_max_steps_validation_error(self):
        """10개 초과 steps → 검증 에러."""
        registry = _create_registry_with(MockFactory("agent_a"))
        executor = PipelineExecutor(registry)
        steps = [PipelineStep(agent_type="agent_a") for _ in range(11)]
        definition = PipelineDefinition(steps=steps)

        errors = await executor.validate(definition)

        assert len(errors) == 1
        assert "maximum" in errors[0]
        assert "10" in errors[0]

    @pytest.mark.asyncio
    async def test_unknown_agent_type_validation_error(self):
        """미등록 agent_type → 검증 에러."""
        registry = _create_registry_with(MockFactory("agent_a"))
        executor = PipelineExecutor(registry)
        steps = [
            PipelineStep(agent_type="agent_a"),
            PipelineStep(agent_type="unknown_agent"),
        ]
        definition = PipelineDefinition(steps=steps)

        errors = await executor.validate(definition)

        assert len(errors) == 1
        assert "unknown_agent" in errors[0]

    @pytest.mark.asyncio
    async def test_valid_pipeline_no_errors(self):
        """유효한 파이프라인 → 에러 없음."""
        registry = _create_registry_with(MockFactory("agent_a"), MockFactory("agent_b"))
        executor = PipelineExecutor(registry)
        steps = [
            PipelineStep(agent_type="agent_a"),
            PipelineStep(agent_type="agent_b"),
        ]
        definition = PipelineDefinition(steps=steps)

        errors = await executor.validate(definition)

        assert errors == []

    @pytest.mark.asyncio
    async def test_exactly_10_steps_is_valid(self):
        """정확히 10개 steps → 유효."""
        registry = _create_registry_with(MockFactory("agent_a"))
        executor = PipelineExecutor(registry)
        steps = [PipelineStep(agent_type="agent_a") for _ in range(10)]
        definition = PipelineDefinition(steps=steps)

        errors = await executor.validate(definition)

        assert errors == []


# ---------------------------------------------------------------------------
# Test: Successful Execution
# ---------------------------------------------------------------------------


class TestPipelineExecution:
    """파이프라인 실행 성공 테스트."""

    @pytest.mark.asyncio
    async def test_single_step_success(self):
        """단일 스텝 실행 성공."""
        artifact = {"type": "agent_a", "formatted_sql": "SELECT 1"}
        registry = _create_registry_with(MockFactory("agent_a", artifact=artifact))
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(
            steps=[PipelineStep(agent_type="agent_a")]
        )

        trace = await executor.execute(definition)

        assert trace.status == "completed"
        assert len(trace.steps) == 1
        assert trace.steps[0].status == "success"
        assert trace.steps[0].agent_type == "agent_a"
        assert trace.steps[0].output_artifact == artifact
        assert trace.total_duration_ms > 0
        assert trace.pipeline_id != ""

    @pytest.mark.asyncio
    async def test_multi_step_success(self):
        """멀티 스텝 실행 성공."""
        artifact_a = {"type": "agent_a", "formatted_sql": "SELECT 1"}
        artifact_b = {"type": "agent_b", "result": "explained"}
        registry = _create_registry_with(
            MockFactory("agent_a", artifact=artifact_a),
            MockFactory("agent_b", artifact=artifact_b),
        )
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(
            steps=[
                PipelineStep(agent_type="agent_a"),
                PipelineStep(agent_type="agent_b"),
            ]
        )

        trace = await executor.execute(definition)

        assert trace.status == "completed"
        assert len(trace.steps) == 2
        assert all(s.status == "success" for s in trace.steps)
        assert trace.total_duration_ms >= sum(s.duration_ms for s in trace.steps)

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_success(self):
        """성공 시 MetricsCollector에 기록됨."""
        from app.framework.metrics import metrics as global_metrics

        global_metrics.reset("pipeline_execution")

        artifact = {"type": "agent_a", "result": "ok"}
        registry = _create_registry_with(MockFactory("agent_a", artifact=artifact))
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(
            steps=[PipelineStep(agent_type="agent_a")]
        )

        await executor.execute(definition)

        metric = global_metrics.get("pipeline_execution")
        assert metric is not None
        assert metric.invocations == 1
        assert metric.successes == 1
        assert metric.total_duration_ms > 0

    @pytest.mark.asyncio
    async def test_sub_command_passed_to_tool(self):
        """sub_command가 tool 입력에 전달됨."""
        artifact = {"type": "agent_a", "formatted_sql": "SELECT 1"}
        registry = _create_registry_with(MockFactory("agent_a", artifact=artifact))
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(
            steps=[PipelineStep(agent_type="agent_a", sub_command="format")]
        )

        trace = await executor.execute(definition)

        assert trace.status == "completed"
        assert trace.steps[0].sub_command == "format"
        assert "sub_command" in trace.steps[0].input_data


# ---------------------------------------------------------------------------
# Test: Step Failure
# ---------------------------------------------------------------------------


class TestPipelineStepFailure:
    """스텝 실패 시 즉시 중단 테스트."""

    @pytest.mark.asyncio
    async def test_step_failure_halts_pipeline(self):
        """스텝 실패 시 즉시 중단, 부분 ExecutionTrace 반환."""
        artifact_a = {"type": "agent_a", "result": "ok"}
        registry = _create_registry_with(
            MockFactory("agent_a", artifact=artifact_a),
            MockFactory("agent_b", should_fail=True),
            MockFactory("agent_c", artifact={"type": "agent_c", "result": "ok"}),
        )
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(
            steps=[
                PipelineStep(agent_type="agent_a"),
                PipelineStep(agent_type="agent_b"),
                PipelineStep(agent_type="agent_c"),
            ]
        )

        trace = await executor.execute(definition)

        assert trace.status == "failed"
        assert len(trace.steps) == 2  # agent_a 성공 + agent_b 실패
        assert trace.steps[0].status == "success"
        assert trace.steps[1].status == "failed"
        assert trace.steps[1].agent_type == "agent_b"

    @pytest.mark.asyncio
    async def test_first_step_failure(self):
        """첫 스텝 실패."""
        registry = _create_registry_with(
            MockFactory("agent_a", should_fail=True),
        )
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(
            steps=[PipelineStep(agent_type="agent_a")]
        )

        trace = await executor.execute(definition)

        assert trace.status == "failed"
        assert len(trace.steps) == 1
        assert trace.steps[0].status == "failed"


# ---------------------------------------------------------------------------
# Test: Input Mapping Resolution
# ---------------------------------------------------------------------------


class TestInputMappingResolution:
    """input_mapping 해석 테스트."""

    @pytest.mark.asyncio
    async def test_input_mapping_from_initial_input(self):
        """첫 스텝은 initial_input에서 매핑 해석."""
        artifact = {"type": "agent_a", "formatted_sql": "SELECT 1"}
        registry = _create_registry_with(MockFactory("agent_a", artifact=artifact))
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(
            steps=[
                PipelineStep(
                    agent_type="agent_a",
                    input_mapping={"sql": "$.raw_sql"},
                )
            ],
            initial_input={"raw_sql": "select * from users"},
        )

        trace = await executor.execute(definition)

        assert trace.status == "completed"
        assert trace.steps[0].input_data["sql"] == "select * from users"

    @pytest.mark.asyncio
    async def test_input_mapping_from_previous_artifact(self):
        """후속 스텝은 이전 artifact에서 매핑 해석."""
        artifact_a = {"type": "agent_a", "formatted_sql": "SELECT 1"}
        artifact_b = {"type": "agent_b", "explanation": "full scan"}
        registry = _create_registry_with(
            MockFactory("agent_a", artifact=artifact_a),
            MockFactory("agent_b", artifact=artifact_b),
        )
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(
            steps=[
                PipelineStep(agent_type="agent_a"),
                PipelineStep(
                    agent_type="agent_b",
                    input_mapping={"query": "$.formatted_sql"},
                ),
            ]
        )

        trace = await executor.execute(definition)

        assert trace.status == "completed"
        assert trace.steps[1].input_data["query"] == "SELECT 1"

    @pytest.mark.asyncio
    async def test_missing_field_in_mapping_halts(self):
        """매핑 필드가 source에 없으면 즉시 중단."""
        artifact_a = {"type": "agent_a", "result": "ok"}
        registry = _create_registry_with(
            MockFactory("agent_a", artifact=artifact_a),
            MockFactory("agent_b", artifact={"type": "agent_b"}),
        )
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(
            steps=[
                PipelineStep(agent_type="agent_a"),
                PipelineStep(
                    agent_type="agent_b",
                    input_mapping={"query": "$.nonexistent_field"},
                ),
            ]
        )

        trace = await executor.execute(definition)

        assert trace.status == "failed"
        assert len(trace.steps) == 2  # agent_a 성공 + agent_b 실패 (매핑 에러)
        assert trace.steps[0].status == "success"
        assert trace.steps[1].status == "failed"
        assert "nonexistent_field" in trace.steps[1].output_artifact["error_message"]
        assert "step 1" in trace.steps[1].output_artifact["error_message"]

    @pytest.mark.asyncio
    async def test_missing_initial_input_field_halts(self):
        """첫 스텝의 매핑 필드가 initial_input에 없으면 즉시 중단."""
        registry = _create_registry_with(MockFactory("agent_a"))
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(
            steps=[
                PipelineStep(
                    agent_type="agent_a",
                    input_mapping={"sql": "$.missing_field"},
                )
            ],
            initial_input={},
        )

        trace = await executor.execute(definition)

        assert trace.status == "failed"
        assert len(trace.steps) == 1
        assert trace.steps[0].status == "failed"
        assert "missing_field" in trace.steps[0].output_artifact["error_message"]
        assert "step 0" in trace.steps[0].output_artifact["error_message"]

    @pytest.mark.asyncio
    async def test_empty_input_mapping_no_error(self):
        """input_mapping이 빈 딕셔너리면 에러 없이 진행."""
        artifact = {"type": "agent_a", "result": "ok"}
        registry = _create_registry_with(MockFactory("agent_a", artifact=artifact))
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(
            steps=[PipelineStep(agent_type="agent_a", input_mapping={})]
        )

        trace = await executor.execute(definition)

        assert trace.status == "completed"

    @pytest.mark.asyncio
    async def test_multiple_mappings_resolved(self):
        """여러 매핑 필드가 모두 해석됨."""
        artifact_a = {"type": "agent_a", "field1": "val1", "field2": "val2"}
        artifact_b = {"type": "agent_b", "result": "ok"}
        registry = _create_registry_with(
            MockFactory("agent_a", artifact=artifact_a),
            MockFactory("agent_b", artifact=artifact_b),
        )
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(
            steps=[
                PipelineStep(agent_type="agent_a"),
                PipelineStep(
                    agent_type="agent_b",
                    input_mapping={"x": "$.field1", "y": "$.field2"},
                ),
            ]
        )

        trace = await executor.execute(definition)

        assert trace.status == "completed"
        assert trace.steps[1].input_data["x"] == "val1"
        assert trace.steps[1].input_data["y"] == "val2"

    @pytest.mark.asyncio
    async def test_input_mapping_without_dollar_prefix(self):
        """$.없이 필드명만 있는 매핑도 동작."""
        artifact = {"type": "agent_a", "result": "ok"}
        registry = _create_registry_with(MockFactory("agent_a", artifact=artifact))
        executor = PipelineExecutor(registry)
        definition = PipelineDefinition(
            steps=[
                PipelineStep(
                    agent_type="agent_a",
                    input_mapping={"sql": "raw_sql"},
                )
            ],
            initial_input={"raw_sql": "SELECT 1"},
        )

        trace = await executor.execute(definition)

        assert trace.status == "completed"
        assert trace.steps[0].input_data["sql"] == "SELECT 1"
