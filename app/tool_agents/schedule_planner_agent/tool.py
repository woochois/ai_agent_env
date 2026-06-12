"""Schedule Planner Agent Tool 구현.

LLM을 호출하여 업무 목록을 분석하고 우선순위 배정 및 일별 일정표를 생성합니다.
업무명, 소요시간, 마감일을 포함한 텍스트를 입력받아 구조화된 일정을 작성합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact
from app.tool_agents._llm_utils import call_llm, parse_json_response

AGENT_TYPE = "schedule_planner_agent"

_SYSTEM_PROMPT = """\
당신은 일정 관리 전문가입니다.
사용자가 제공하는 업무 목록(업무명, 소요시간, 마감일)을 분석하여 우선순위를 배정하고 일별 일정표를 생성해주세요.

작성 규칙:
- 마감일이 임박한 업무에 높은 우선순위를 부여합니다.
- 소요시간을 고려하여 하루 근무시간(8시간) 내에 배분합니다.
- 의존관계가 있는 경우 순서를 반영합니다.
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


class SchedulePlannerInput(BaseModel):
    """Schedule Planner Tool 입력 스키마."""

    tasks: str = Field(..., description="업무 목록 텍스트 (업무명, 소요시간, 마감일 포함)")
    start_date: str = Field(default="", description="시작일 (선택, YYYY-MM-DD)")


class SchedulePlannerTool(BaseAgentTool):
    """LLM을 호출하여 업무 우선순위 및 일별 일정표를 생성하는 Tool."""

    name: str = "schedule_planner"
    description: str = (
        "업무 목록과 마감일을 입력하면 우선순위와 일별 일정 제안을 생성합니다. "
        "업무명, 소요시간, 마감일을 포함한 텍스트를 입력하세요."
    )
    args_schema: type[BaseModel] = SchedulePlannerInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(
        self,
        tasks: str,
        start_date: str = "",
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("SchedulePlannerTool은 비동기 전용입니다. _arun을 사용하세요.")

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="일정 계획 생성 중 오류가 발생했습니다",
    )
    async def _arun(
        self,
        tasks: str,
        start_date: str = "",
        config: RunnableConfig | None = None,
    ) -> tuple[str, dict]:
        user_input = f"업무 목록:\n{tasks}"
        if start_date:
            user_input += f"\n\n시작일: {start_date}"

        response_text = await call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_input=user_input,
        )

        parsed = parse_json_response(response_text)

        if parsed and "tasks" in parsed and "schedule" in parsed:
            task_list = parsed["tasks"]
            schedule = parsed["schedule"]
            priorities = parsed.get("priorities", [])
        else:
            # JSON 파싱 실패 시 기본 구조 생성
            task_list = []
            schedule = []
            priorities = []

        artifact: dict = {
            "type": AGENT_TYPE,
            "tasks": task_list,
            "schedule": schedule,
            "priorities": priorities,
        }

        content = self._format_to_markdown(artifact)
        return content, artifact

    def _format_to_markdown(self, art: dict) -> str:
        """artifact를 마크다운 문자열로 변환합니다."""
        lines = ["## 📅 일정 계획\n"]

        # 우선순위 섹션
        priorities = art.get("priorities", [])
        if priorities:
            lines.append("### 우선순위")
            for p in priorities:
                lines.append(f"- {p}")
            lines.append("")

        # 업무 목록 섹션
        task_list = art.get("tasks", [])
        if task_list:
            lines.append("### 업무 목록")
            for t in task_list:
                name = t.get("name", "")
                hours = t.get("estimated_hours", "")
                deadline = t.get("deadline", "")
                priority = t.get("priority", "")
                lines.append(f"- **{name}** | {hours}시간 | 마감: {deadline} | 우선순위: {priority}")
            lines.append("")

        # 일별 일정 섹션
        schedule = art.get("schedule", [])
        if schedule:
            lines.append("### 일별 일정")
            for day in schedule:
                date = day.get("date", "")
                day_tasks = day.get("tasks", [])
                lines.append(f"**{date}**")
                for dt in day_tasks:
                    lines.append(f"  - {dt}")
            lines.append("")

        return "\n".join(lines)

    def format_content(self, message: ToolMessage) -> ToolMessage:
        """artifact를 마크다운으로 변환하여 LLM에게 전달합니다."""
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if "error_message" in art:
            return message

        md = self._format_to_markdown(art)
        return message.model_copy(update={"content": md})
