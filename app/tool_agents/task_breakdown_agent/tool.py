"""Task Breakdown Agent Tool 구현.

LLM을 호출하여 프로젝트를 WBS(Work Breakdown Structure)로 분해하고
의존관계와 소요시간을 추정합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact
from app.tool_agents._llm_utils import call_llm, parse_json_response

AGENT_TYPE = "task_breakdown_agent"

_SYSTEM_PROMPT = """\
당신은 프로젝트 관리 전문가입니다.
사용자가 제공하는 프로젝트 설명과 목표를 바탕으로 WBS(Work Breakdown Structure)를 생성합니다.

분해 규칙:
- 각 태스크는 명확하고 실행 가능한 단위로 분해합니다.
- 각 태스크에 예상 소요시간(시간 단위)을 추정합니다.
- 우선순위(high/medium/low)를 지정합니다.
- 태스크 간 의존관계를 명시합니다.
- 제약 조건이 있으면 이를 반영합니다.
- 프로젝트 전체 예상 소요시간을 합산합니다.

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

dependencies 배열의 각 항목 [A, B]는 "A를 완료해야 B를 시작할 수 있다"를 의미합니다.
"""


class TaskBreakdownInput(BaseModel):
    """Task Breakdown Tool 입력 스키마."""

    project: str = Field(..., description="프로젝트 설명")
    goal: str = Field(..., description="프로젝트 목표")
    constraints: str = Field(default="", description="제약 조건 (선택)")


class TaskBreakdownTool(BaseAgentTool):
    """LLM을 호출하여 프로젝트를 WBS로 분해하는 Tool."""

    name: str = "task_breakdown"
    description: str = (
        "프로젝트를 WBS로 분해하여 태스크 목록, 의존관계, 소요시간을 추정합니다. "
        "프로젝트 설명과 목표를 입력하면 구조화된 업무 분해 결과를 반환합니다."
    )
    args_schema: type[BaseModel] = TaskBreakdownInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(
        self,
        project: str,
        goal: str,
        constraints: str = "",
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("TaskBreakdownTool은 비동기 전용입니다. _arun을 사용하세요.")

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="업무 분해 중 오류가 발생했습니다",
    )
    async def _arun(
        self,
        project: str,
        goal: str,
        constraints: str = "",
        config: RunnableConfig | None = None,
    ) -> tuple[str, dict]:
        user_input = (
            f"프로젝트: {project}\n"
            f"목표: {goal}\n"
        )
        if constraints:
            user_input += f"제약 조건: {constraints}\n"

        response_text = await call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_input=user_input,
        )

        parsed = parse_json_response(response_text)

        if parsed and "tasks" in parsed:
            project_name = parsed.get("project_name", project)
            tasks = parsed.get("tasks", [])
            dependencies = parsed.get("dependencies", [])
            total_estimated_hours = parsed.get("total_estimated_hours", 0)
        else:
            project_name = project
            tasks = []
            dependencies = []
            total_estimated_hours = 0

        artifact: dict = {
            "type": AGENT_TYPE,
            "project_name": project_name,
            "tasks": tasks,
            "dependencies": dependencies,
            "total_estimated_hours": total_estimated_hours,
        }

        content = self._build_content(
            project_name, tasks, dependencies,
            total_estimated_hours, response_text, parsed,
        )
        return content, artifact

    def _build_content(
        self,
        project_name: str,
        tasks: list,
        dependencies: list,
        total_estimated_hours: int,
        response_text: str,
        parsed: dict | None,
    ) -> str:
        """LLM 응답을 사용자 친화적 텍스트로 변환합니다."""
        if not parsed:
            return response_text

        lines = [
            f"프로젝트: {project_name}",
            f"총 예상 소요시간: {total_estimated_hours}시간",
        ]

        if tasks:
            lines.append("\n태스크 목록:")
            for i, task in enumerate(tasks, 1):
                name = task.get("task_name", "")
                hours = task.get("estimated_hours", 0)
                priority = task.get("priority", "medium")
                deps = task.get("dependencies", [])
                dep_str = f" (선행: {', '.join(deps)})" if deps else ""
                lines.append(f"  {i}. [{priority}] {name} - {hours}시간{dep_str}")

        if dependencies:
            lines.append("\n의존관계:")
            for dep in dependencies:
                if len(dep) == 2:
                    lines.append(f"  {dep[0]} → {dep[1]}")

        return "\n".join(lines)

    def format_content(self, message: ToolMessage) -> ToolMessage:
        """artifact를 마크다운으로 변환하여 LLM에게 전달합니다."""
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if "error_message" in art:
            return message

        project_name = art.get("project_name", "")
        tasks = art.get("tasks", [])
        dependencies = art.get("dependencies", [])
        total_hours = art.get("total_estimated_hours", 0)

        md_lines = [
            f"## 📋 업무 분해 (WBS)\n",
            f"**프로젝트:** {project_name}\n",
            f"**총 예상 소요시간:** {total_hours}시간\n",
            "---\n",
        ]

        if tasks:
            md_lines.append("### 태스크 목록\n")
            md_lines.append("| # | 태스크 | 설명 | 소요시간 | 우선순위 | 선행 태스크 |")
            md_lines.append("|---|--------|------|----------|----------|------------|")
            for i, task in enumerate(tasks, 1):
                name = task.get("task_name", "")
                desc = task.get("description", "")
                hours = task.get("estimated_hours", 0)
                priority = task.get("priority", "medium")
                deps = ", ".join(task.get("dependencies", [])) or "-"
                md_lines.append(f"| {i} | {name} | {desc} | {hours}h | {priority} | {deps} |")
            md_lines.append("")

        if dependencies:
            md_lines.append("### 의존관계\n")
            for dep in dependencies:
                if len(dep) == 2:
                    md_lines.append(f"- {dep[0]} → {dep[1]}")
            md_lines.append("")

        md = "\n".join(md_lines)
        return message.model_copy(update={"content": md})
