"""Pipeline API 라우터.

파이프라인 실행을 HTTP API로 노출합니다.

엔드포인트:
    POST /supervisor/pipeline - 파이프라인 정의를 받아 순차 실행
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.framework.pipeline import (
    ExecutionTrace,
    PipelineDefinition,
    PipelineExecutor,
)
from app.framework.registry import registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/supervisor", tags=["supervisor"])


@router.post(
    "/pipeline",
    summary="Agent Pipeline 순차 실행",
    description="파이프라인 정의(steps 배열)를 받아 순차 실행하고 ExecutionTrace를 반환합니다. "
    "각 step의 output artifact가 다음 step의 input으로 input_mapping을 통해 전달됩니다.",
    responses={
        200: {"description": "파이프라인 실행 완료 (completed 또는 failed)"},
        422: {"description": "검증 에러 (빈 steps, 초과 steps, 미등록 agent_type 등)"},
    },
)
async def execute_pipeline(
    definition: PipelineDefinition,
) -> JSONResponse:
    """파이프라인을 실행합니다.

    파이프라인 정의를 검증한 후 순차 실행하고, ExecutionTrace를 반환합니다.

    - HTTP 200: 파이프라인 실행 완료 (completed 또는 failed)
    - HTTP 422: 검증 에러 (빈 steps, 초과 steps, 미등록 agent_type 등)

    Args:
        definition: PipelineDefinition (steps 배열 + initial_input).
            - steps: 순차 실행할 스텝 목록 (최대 10개)
            - steps[].agent_type: 실행할 agent 타입 (Agent_Registry에 등록된 이름)
            - steps[].sub_command: agent 내 서브커맨드 (optional)
            - steps[].input_mapping: 이전 스텝 artifact에서 입력 매핑 (예: {"query": "$.formatted_sql"})
            - initial_input: 첫 번째 스텝의 input_mapping 소스 데이터
    """
    registry.discover()
    executor = PipelineExecutor(registry)

    # 사전 검증
    errors = await executor.validate(definition)
    if errors:
        trace = ExecutionTrace(
            pipeline_id="",
            steps=[],
            total_duration_ms=0.0,
            status="validation_error",
        )
        return JSONResponse(
            status_code=422,
            content={
                "errors": errors,
                "trace": trace.model_dump(),
            },
        )

    # 파이프라인 실행
    trace = await executor.execute(definition)
    return JSONResponse(
        status_code=200,
        content=trace.model_dump(),
    )
