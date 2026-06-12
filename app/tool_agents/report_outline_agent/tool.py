"""Report Outline Agent Tool 구현.

LLM을 호출하여 보고서 개요(목차 및 섹션별 요점)를 생성합니다. 주제, 목적,
대상 독자(executive/technical/general)를 입력받아 구조화된 보고서 목차를 작성합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact
from app.tool_agents._llm_utils import call_llm, parse_json_response

AGENT_TYPE = "report_outline_agent"

_SYSTEM_PROMPT = """\
당신은 보고서 구성 전문가입니다.
사용자가 제공하는 주제, 목적, 대상 독자를 바탕으로 체계적인 보고서 목차와 섹션별 요점, 작성 가이드를 생성해주세요.

작성 규칙:
- 목차는 논리적 흐름에 따라 구성합니다.
- 각 섹션에는 핵심 요점(key_points)을 포함합니다.
- 필요한 경우 하위 섹션(subsections)을 포함합니다.
- 대상 독자 수준을 반영합니다:
  - executive: 핵심 요약 중심, 의사결정 지원 관점
  - technical: 상세 기술 내용, 데이터/근거 중심
  - general: 이해하기 쉬운 일반적 구성

반드시 아래 JSON 형식으로만 응답하세요:
```json
{
  "topic": "보고서 주제",
  "purpose": "보고서 목적",
  "outline_sections": [
    {
      "title": "섹션 제목",
      "key_points": ["요점1", "요점2"],
      "subsections": [
        {"title": "하위 섹션 제목", "key_points": ["세부 요점1"]}
      ]
    }
  ]
}
```
"""


class ReportOutlineInput(BaseModel):
    """Report Outline Tool 입력 스키마."""

    topic: str = Field(..., description="보고서 주제")
    purpose: str = Field(..., description="보고서 목적")
    audience: str = Field(
        default="general",
        description="대상 독자 (executive | technical | general)",
    )


class ReportOutlineTool(BaseAgentTool):
    """LLM을 호출하여 보고서 개요(목차/요점)를 생성하는 Tool."""

    name: str = "report_outline"
    description: str = (
        "보고서 개요를 작성합니다. "
        "주제, 목적, 대상 독자를 입력하면 목차와 섹션별 요점을 제안합니다."
    )
    args_schema: type[BaseModel] = ReportOutlineInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(
        self,
        topic: str,
        purpose: str,
        audience: str = "general",
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("ReportOutlineTool은 비동기 전용입니다. _arun을 사용하세요.")

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="보고서 개요 생성 중 오류가 발생했습니다",
    )
    async def _arun(
        self,
        topic: str,
        purpose: str,
        audience: str = "general",
        config: RunnableConfig | None = None,
    ) -> tuple[str, dict]:
        user_input = (
            f"주제: {topic}\n"
            f"목적: {purpose}\n"
            f"대상 독자: {audience}"
        )

        response_text = await call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_input=user_input,
        )

        parsed = parse_json_response(response_text)

        if parsed and "outline_sections" in parsed:
            outline_topic = parsed.get("topic", topic)
            outline_purpose = parsed.get("purpose", purpose)
            outline_sections = parsed["outline_sections"]
        else:
            # JSON 파싱 실패 시 기본 구조 생성
            outline_topic = topic
            outline_purpose = purpose
            outline_sections = [
                {"title": "개요", "key_points": [response_text], "subsections": []}
            ]

        artifact: dict = {
            "type": AGENT_TYPE,
            "topic": outline_topic,
            "purpose": outline_purpose,
            "outline_sections": outline_sections,
        }

        content = self._format_to_markdown(artifact)
        return content, artifact

    def _format_to_markdown(self, artifact: dict) -> str:
        """artifact를 마크다운 문자열로 변환합니다."""
        topic = artifact.get("topic", "")
        purpose = artifact.get("purpose", "")
        sections = artifact.get("outline_sections", [])

        lines: list[str] = [
            f"## 📋 보고서 개요: {topic}",
            "",
            f"**목적:** {purpose}",
            "",
            "---",
            "",
        ]

        for i, section in enumerate(sections, 1):
            title = section.get("title", "")
            key_points = section.get("key_points", [])
            subsections = section.get("subsections", [])

            lines.append(f"### {i}. {title}")
            for point in key_points:
                lines.append(f"- {point}")

            if subsections:
                lines.append("")
                for sub in subsections:
                    sub_title = sub.get("title", "")
                    sub_points = sub.get("key_points", [])
                    lines.append(f"  #### {sub_title}")
                    for sp in sub_points:
                        lines.append(f"  - {sp}")

            lines.append("")

        return "\n".join(lines)

    def format_content(self, message: ToolMessage) -> ToolMessage:
        """artifact를 마크다운으로 변환하여 LLM에게 전달합니다."""
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if "error_message" in art:
            return message

        content = self._format_to_markdown(art)
        return message.model_copy(update={"content": content})
