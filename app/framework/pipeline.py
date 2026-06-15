"""Agent Pipeline (체이닝) 실행기.

여러 Tool Agent를 순차적으로 연결하여 이전 Agent의 출력(artifact)을
다음 Agent의 입력으로 전달하는 파이프라인을 실행합니다.

- PipelineStep: 단일 파이프라인 스텝 정의
- PipelineDefinition: 파이프라인 전체 정의 (steps 배열 + initial_input)
- StepResult: 개별 스텝 실행 결과
- ExecutionTrace: 파이프라인 전체 실행 추적 기록
- PipelineExecutor: 파이프라인 검증 및 순차 실행기
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.framework.metrics import metrics
from app.framework.registry import ToolAgentRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class PipelineStep(BaseModel):
    """단일 파이프라인 스텝 정의."""

    agent_type: str
    sub_command: str | None = None
    input_mapping: dict[str, str] = Field(default_factory=dict)


class PipelineDefinition(BaseModel):
    """파이프라인 전체 정의."""

    steps: list[PipelineStep]
    initial_input: dict[str, Any] = Field(default_factory=dict)


class StepResult(BaseModel):
    """개별 스텝 실행 결과."""

    step_index: int
    agent_type: str
    sub_command: str | None
    input_data: dict[str, Any]
    output_artifact: dict[str, Any]
    duration_ms: float
    status: str  # "success" | "failed"


class ExecutionTrace(BaseModel):
    """파이프라인 전체 실행 추적 기록."""

    pipeline_id: str
    steps: list[StepResult]
    total_duration_ms: float
    status: str  # "completed" | "failed" | "validation_error"


# ---------------------------------------------------------------------------
# PipelineExecutor
# ---------------------------------------------------------------------------


class PipelineExecutor:
    """파이프라인 정의를 받아 순차 실행하는 실행기.

    Agent_Registry를 참조하여 각 step의 Tool을 생성하고 순차 실행합니다.
    LLM 개입 없이 정의된 순서대로 Agent를 실행합니다 (deterministic pipeline).
    """

    MAX_STEPS = 10

    def __init__(self, registry: ToolAgentRegistry) -> None:
        self._registry = registry

    async def validate(self, definition: PipelineDefinition) -> list[str]:
        """파이프라인 정의를 사전 검증합니다.

        Args:
            definition: 검증할 파이프라인 정의.

        Returns:
            에러 메시지 목록. 비어있으면 유효함.
        """
        errors: list[str] = []

        # 빈 steps 검증
        if not definition.steps:
            errors.append("Pipeline requires at least 1 step")
            return errors

        # 최대 step 수 검증
        if len(definition.steps) > self.MAX_STEPS:
            errors.append(
                f"Pipeline exceeds maximum of {self.MAX_STEPS} steps "
                f"(got {len(definition.steps)})"
            )
            return errors

        # agent_type 존재 여부 검증
        missing_types: list[str] = []
        for step in definition.steps:
            if self._registry.get_factory(step.agent_type) is None:
                if step.agent_type not in missing_types:
                    missing_types.append(step.agent_type)

        if missing_types:
            errors.append(
                f"Unknown agent_types: {missing_types}. "
                f"Available: {self._registry.available_types()}"
            )

        return errors

    async def execute(self, definition: PipelineDefinition) -> ExecutionTrace:
        """파이프라인을 순차 실행합니다.

        Args:
            definition: 실행할 파이프라인 정의.

        Returns:
            실행 추적 기록(ExecutionTrace).
        """
        pipeline_id = str(uuid.uuid4())
        pipeline_start = time.perf_counter()
        step_results: list[StepResult] = []

        # 이전 스텝의 artifact (첫 스텝은 initial_input 사용)
        previous_artifact: dict[str, Any] = definition.initial_input

        for idx, step in enumerate(definition.steps):
            step_start = time.perf_counter()

            # input_mapping 해석
            try:
                input_data = self._resolve_input_mapping(
                    step.input_mapping, previous_artifact, idx
                )
            except InputMappingError as exc:
                # 매핑 실패 시 즉시 중단
                step_result = StepResult(
                    step_index=idx,
                    agent_type=step.agent_type,
                    sub_command=step.sub_command,
                    input_data={},
                    output_artifact={"error_message": str(exc)},
                    duration_ms=(time.perf_counter() - step_start) * 1000,
                    status="failed",
                )
                step_results.append(step_result)
                total_duration = (time.perf_counter() - pipeline_start) * 1000
                return ExecutionTrace(
                    pipeline_id=pipeline_id,
                    steps=step_results,
                    total_duration_ms=total_duration,
                    status="failed",
                )

            # sub_command가 있으면 input_data에 추가
            if step.sub_command is not None:
                input_data["sub_command"] = step.sub_command

            # Tool 생성 및 실행
            try:
                factory = self._registry.get_factory(step.agent_type)
                if factory is None:
                    raise ValueError(f"Agent type '{step.agent_type}' not found")

                tool_config = {
                    "type": step.agent_type,
                    "name": step.agent_type,
                    "description": f"Pipeline step {idx}",
                }
                tool = factory.create_tool(tool_config)

                # Tool 실행 (BaseTool.ainvoke)
                result = await tool.ainvoke(input=input_data)

                # 결과에서 artifact 추출
                if isinstance(result, tuple) and len(result) == 2:
                    _, artifact = result
                elif isinstance(result, dict):
                    artifact = result
                else:
                    artifact = {"result": str(result)}

                # 에러 아티팩트 감지
                is_error = "error_message" in artifact if isinstance(artifact, dict) else False
                status = "failed" if is_error else "success"

            except Exception as exc:
                artifact = {"error_message": str(exc)}
                status = "failed"

            step_duration = (time.perf_counter() - step_start) * 1000
            step_result = StepResult(
                step_index=idx,
                agent_type=step.agent_type,
                sub_command=step.sub_command,
                input_data=input_data,
                output_artifact=artifact if isinstance(artifact, dict) else {"result": str(artifact)},
                duration_ms=step_duration,
                status=status,
            )
            step_results.append(step_result)

            # 실패 시 즉시 중단
            if status == "failed":
                total_duration = (time.perf_counter() - pipeline_start) * 1000
                return ExecutionTrace(
                    pipeline_id=pipeline_id,
                    steps=step_results,
                    total_duration_ms=total_duration,
                    status="failed",
                )

            # 성공 시 현재 artifact를 다음 스텝의 소스로 설정
            previous_artifact = artifact if isinstance(artifact, dict) else {}

        # 모든 스텝 성공
        total_duration = (time.perf_counter() - pipeline_start) * 1000

        # MetricsCollector에 기록
        metrics.record(
            "pipeline_execution",
            success=True,
            duration_ms=total_duration,
        )

        return ExecutionTrace(
            pipeline_id=pipeline_id,
            steps=step_results,
            total_duration_ms=total_duration,
            status="completed",
        )

    def _resolve_input_mapping(
        self,
        input_mapping: dict[str, str],
        source: dict[str, Any],
        step_index: int,
    ) -> dict[str, Any]:
        """input_mapping 식을 해석하여 입력 데이터를 구성합니다.

        "$.field_name" 형태의 표현식을 source dict에서 해당 값을 추출합니다.

        Args:
            input_mapping: {target_field: "$.source_field"} 매핑.
            source: 이전 스텝의 artifact 또는 initial_input.
            step_index: 현재 스텝 인덱스 (에러 메시지용).

        Returns:
            해석된 입력 데이터 딕셔너리.

        Raises:
            InputMappingError: 참조된 필드가 source에 없는 경우.
        """
        if not input_mapping:
            return {}

        resolved: dict[str, Any] = {}
        for target_field, expression in input_mapping.items():
            # "$.field_name" 파싱
            if expression.startswith("$."):
                source_field = expression[2:]
            else:
                source_field = expression

            if source_field not in source:
                raise InputMappingError(
                    f"Field '{source_field}' not found in source at step {step_index}. "
                    f"Available fields: {list(source.keys())}"
                )

            resolved[target_field] = source[source_field]

        return resolved


class InputMappingError(Exception):
    """input_mapping 해석 실패 시 발생하는 예외."""

    pass
