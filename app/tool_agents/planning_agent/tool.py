"""Planning Agent Tool 구현.

기존 task_breakdown, schedule_planner 에이전트를
단일 Expert Agent로 통합합니다. sub_command 파라미터를 통해 내부 라우팅합니다.

Sub_Commands:
- breakdown_task: 프로젝트 WBS 분해
- plan_schedule: 일정 계획 생성

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import (
    BaseAgentTool,
    auto_error_artifact,
    build_artifact,
    build_error_artifact,
)
from app.tool_agents._llm_utils import call_llm, parse_json_response

AGENT_TYPE = "planning"

_VALID_COMMANDS = frozenset({"breakdown_task", "plan_schedule"})

# Required fields per sub_command
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "breakdown_task": ["project", "goal"],
    "plan_schedule": ["tasks"],
}

# --- System Prompts ---

_BREAKDOWN_SYSTEM_PROMPT = """\
당신은 프로젝트 관리 전문가입니다.
사용자가 제공하는 프로젝트 설명과 목표를 바탕으로 WBS(Work Breakdown Structure)를 생성합니다.

분해 규칙:
- 각 태스크는 명확하고 실행 가능한 단위로 분해합니다.
- 각 태스크에 예상 소요시간(시간 단위)을 추정합니다.
- 우선순위(high/medium/low)를 지정합니다.
- 태스크 간 의존관계를 명시합니다.

반드시 아래 JSON 형식으로만 응답하세요:
```json
{
  "project_name": "프로젝트명",
  "tasks": [
    {
      "task_name": "태스크명",
      "description": "설명",
      "estimated_hours": 8,
      "priority": "high",
      "dependencies": ["선행 태스크명"]
    }
  ],
  "dependencies": [["태스크A", "태스크B"]],
  "total_estimated_hours": 120
}
```
"""

_SCHEDULE_SYSTEM_PROMPT = """\
당신은 일정 관리 전문가입니다.
사용자가 제공하는 업무 목록을 분석하여 우선순위를 배정하고 일별 일정표를 생성해주세요.

작성 규칙:
- 마감일이 임박한 업무에 높은 우선순위를 부여합니다.
- 소요시간을 고려하여 하루 근무시간(8시간) 내에 배분합니다.
- 각 업무에 high/medium/low 우선순위를 부여합니다.

반드시 아래 JSON 형식으로만 응답하세요:
```json
{
  "tasks": [
    {"name": "업무명", "estimated_hours": 4, "deadline": "2024-01-15", "priority": "high"}
  ],
  "schedule": [
    {"date": "2024-01-10", "tasks": ["업무1", "업무2"]}
  ],
  "priorities": ["high: 업무1", "medium: 업무3"]
}
```
"""


class PlanningInput(BaseModel):
    """Planning Agent 입력 스키마."""

    sub_command: str = Field(
        ..., description="실행할 서브커맨드: breakdown_task | plan_schedule"
    )
    project: str = Field(default="", description="프로젝트 설명 (breakdown_task용)")
    goal: str = Field(default="", description="프로젝트 목표 (breakdown_task용)")
    constraints: str = Field(default="", description="제약 조건 (breakdown_task용, 선택)")
    tasks: str = Field(default="", description="업무 목록 텍스트 (plan_schedule용)")
    start_date: str = Field(default="", description="시작일 (plan_schedule용, 선택)")


class PlanningTool(BaseAgentTool):
    """통합 Planning Agent Tool.

    sub_command에 따라 적절한 내부 핸들러로 라우팅합니다.
    """

    name: str = "planning"
    description: str = (
        "계획 관련 작업을 수행합니다. breakdown_task(프로젝트 WBS 분해), "
        "plan_schedule(일정 계획 생성)을 지원합니다."
    )
    args_schema: type[BaseModel] = PlanningInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(
        self,
        sub_command: str,
        project: str = "",
        goal: str = "",
        constraints: str = "",
        tasks: str = "",
        start_date: str = "",
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("비동기(_arun)로만 실행됩니다")

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="Planning Agent 실행 중 오류가 발생했습니다")
    async def _arun(
        self,
        sub_command: str,
        project: str = "",
        goal: str = "",
        constraints: str = "",
        tasks: str = "",
        start_date: str = "",
        config: RunnableConfig | None = None,
    ) -> tuple[str, dict]:
        # Sub_command 검증
        if sub_command not in _VALID_COMMANDS:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message=f"Unknown sub_command: '{sub_command}'",
                error_detail=f"Valid sub_commands: {sorted(_VALID_COMMANDS)}",
                sub_command=sub_command,
                valid_commands=sorted(_VALID_COMMANDS),
            )

        # 입력 필드 검증
        missing = self._validate_inputs(
            sub_command,
            project=project,
            goal=goal,
            tasks=tasks,
        )
        if missing:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message=f"필수 입력 필드가 누락되었습니다: {missing}",
                error_detail=f"sub_command '{sub_command}'에 필요한 필드: {_REQUIRED_FIELDS[sub_command]}",
                sub_command=sub_command,
                missing_fields=missing,
            )

        # 핸들러 디스패치
        handler = getattr(self, f"_handle_{sub_command}")
        return await handler(
            project=project,
            goal=goal,
            constraints=constraints,
            tasks=tasks,
            start_date=start_date,
        )

    def _validate_inputs(
        self,
        sub_command: str,
        project: str = "",
        goal: str = "",
        tasks: str = "",
    ) -> list[str]:
        """서브커맨드별 필수 입력 필드를 검증합니다."""
        missing = []
        required = _REQUIRED_FIELDS.get(sub_command, [])
        field_values = {
            "project": project,
            "goal": goal,
            "tasks": tasks,
        }
        for field in required:
            val = field_values.get(field, "")
            if not val or not val.strip():
                missing.append(field)
        return missing

    async def _handle_breakdown_task(self, project: str, goal: str, constraints: str = "", **kwargs: Any) -> tuple[str, dict]:
        """breakdown_task 서브커맨드: 프로젝트 WBS 분해."""
        user_input = f"프로젝트: {project}\n목표: {goal}\n"
        if constraints:
            user_input += f"제약 조건: {constraints}\n"

        try:
            response_text = await call_llm(
                system_prompt=_BREAKDOWN_SYSTEM_PROMPT,
                user_input=user_input,
            )
        except Exception as exc:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message=f"LLM 호출 실패: {exc}",
                sub_command="breakdown_task",
            )

        parsed = parse_json_response(response_text)

        if parsed and "tasks" in parsed:
            return "", build_artifact(
                AGENT_TYPE,
                sub_command="breakdown_task",
                project_name=parsed.get("project_name", project),
                tasks=parsed.get("tasks", []),
                dependencies=parsed.get("dependencies", []),
                total_estimated_hours=parsed.get("total_estimated_hours", 0),
            )
        else:
            # JSON 파싱 실패 시 raw text를 content로 사용
            return "", build_artifact(
                AGENT_TYPE,
                sub_command="breakdown_task",
                content=response_text,
            )

    async def _handle_plan_schedule(self, tasks: str, start_date: str = "", **kwargs: Any) -> tuple[str, dict]:
        """plan_schedule 서브커맨드: 일정 계획 생성."""
        user_input = f"업무 목록:\n{tasks}"
        if start_date:
            user_input += f"\n\n시작일: {start_date}"

        try:
            response_text = await call_llm(
                system_prompt=_SCHEDULE_SYSTEM_PROMPT,
                user_input=user_input,
            )
        except Exception as exc:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message=f"LLM 호출 실패: {exc}",
                sub_command="plan_schedule",
            )

        parsed = parse_json_response(response_text)

        if parsed and "tasks" in parsed:
            return "", build_artifact(
                AGENT_TYPE,
                sub_command="plan_schedule",
                tasks=parsed.get("tasks", []),
                schedule=parsed.get("schedule", []),
                priorities=parsed.get("priorities", []),
            )
        else:
            # JSON 파싱 실패 시 raw text를 content로 사용
            return "", build_artifact(
                AGENT_TYPE,
                sub_command="plan_schedule",
                content=response_text,
            )
