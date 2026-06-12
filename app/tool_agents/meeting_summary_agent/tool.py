"""Meeting Summary Agent Tool 구현.

LLM을 호출하여 회의 내용을 구조화된 요약으로 변환합니다. 참석자, 안건,
결정사항, 액션아이템을 추출하여 정리합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact
from app.tool_agents._llm_utils import call_llm, parse_json_response

AGENT_TYPE = "meeting_summary_agent"

_SYSTEM_PROMPT = """\
당신은 회의록 전문 비서입니다.
사용자가 제공하는 회의 내용(녹취록, 메모 등)을 분석하여 구조화된 회의록 요약을 작성해주세요.

추출 항목:
- title: 회의 제목 (사용자가 제공하지 않으면 내용에서 추론)
- attendees: 참석자 목록
- agenda: 논의 안건 목록
- decisions: 결정사항 목록
- action_items: 액션아이템 목록 (각 항목에 담당자, 업무내용, 마감일 포함)

작성 규칙:
- 내용에서 명확히 언급된 정보만 추출합니다.
- 참석자가 명시되지 않은 경우 빈 배열로 둡니다.
- 마감일이 명시되지 않은 경우 "미정"으로 표기합니다.

반드시 아래 JSON 형식으로만 응답하세요:
```json
{
  "title": "회의 제목",
  "attendees": ["참석자1", "참석자2"],
  "agenda": ["안건1", "안건2"],
  "decisions": ["결정사항1", "결정사항2"],
  "action_items": [
    {"assignee": "담당자", "task": "업무내용", "deadline": "마감일"}
  ]
}
```
"""


class MeetingSummaryInput(BaseModel):
    """Meeting Summary Tool 입력 스키마."""

    content: str = Field(..., description="회의 내용 텍스트 (녹취록, 메모 등)")
    meeting_title: str = Field(default="", description="회의 제목 (선택)")


class MeetingSummaryTool(BaseAgentTool):
    """LLM을 호출하여 회의 내용을 구조화된 요약으로 변환하는 Tool."""

    name: str = "meeting_summary"
    description: str = (
        "회의 내용을 구조화된 요약으로 변환합니다. "
        "참석자, 안건, 결정사항, 액션아이템을 추출하여 정리합니다."
    )
    args_schema: type[BaseModel] = MeetingSummaryInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(
        self,
        content: str,
        meeting_title: str = "",
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("MeetingSummaryTool은 비동기 전용입니다. _arun을 사용하세요.")

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="회의록 요약 생성 중 오류가 발생했습니다",
    )
    async def _arun(
        self,
        content: str,
        meeting_title: str = "",
        config: RunnableConfig | None = None,
    ) -> tuple[str, dict]:
        user_input = ""
        if meeting_title:
            user_input += f"회의 제목: {meeting_title}\n\n"
        user_input += f"회의 내용:\n{content}"

        response_text = await call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_input=user_input,
        )

        parsed = parse_json_response(response_text)

        if parsed and "title" in parsed:
            title = parsed["title"]
            attendees = parsed.get("attendees", [])
            agenda = parsed.get("agenda", [])
            decisions = parsed.get("decisions", [])
            action_items = parsed.get("action_items", [])
        else:
            # JSON 파싱 실패 시 기본값 사용
            title = meeting_title or "회의록"
            attendees = []
            agenda = []
            decisions = []
            action_items = []

        artifact: dict = {
            "type": AGENT_TYPE,
            "title": title,
            "attendees": attendees,
            "agenda": agenda,
            "decisions": decisions,
            "action_items": action_items,
        }

        # content: 파싱 성공 시 마크다운 요약, 실패 시 원본 응답
        if parsed and "title" in parsed:
            content_text = self._build_markdown(artifact)
        else:
            content_text = response_text

        return content_text, artifact

    def _build_markdown(self, artifact: dict) -> str:
        """artifact를 마크다운 형식으로 변환합니다."""
        lines = [f"## 📋 {artifact['title']}\n"]

        if artifact["attendees"]:
            lines.append("### 참석자")
            lines.append(", ".join(artifact["attendees"]))
            lines.append("")

        if artifact["agenda"]:
            lines.append("### 안건")
            for item in artifact["agenda"]:
                lines.append(f"- {item}")
            lines.append("")

        if artifact["decisions"]:
            lines.append("### 결정사항")
            for item in artifact["decisions"]:
                lines.append(f"- {item}")
            lines.append("")

        if artifact["action_items"]:
            lines.append("### 액션아이템")
            for item in artifact["action_items"]:
                assignee = item.get("assignee", "미지정")
                task = item.get("task", "")
                deadline = item.get("deadline", "미정")
                lines.append(f"- **{assignee}**: {task} (마감: {deadline})")
            lines.append("")

        return "\n".join(lines)

    def format_content(self, message: ToolMessage) -> ToolMessage:
        """artifact를 마크다운으로 변환하여 LLM에게 전달합니다."""
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if "error_message" in art:
            return message

        md = self._build_markdown(art)
        return message.model_copy(update={"content": md})
