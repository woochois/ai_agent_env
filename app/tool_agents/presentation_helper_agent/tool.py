"""Presentation Helper Agent Tool 구현.

LLM을 호출하여 발표 자료의 슬라이드 구성, 각 슬라이드별 스크립트,
시간 배분을 생성합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact
from app.tool_agents._llm_utils import call_llm, parse_json_response

AGENT_TYPE = "presentation_helper_agent"

_SYSTEM_PROMPT = """\
당신은 발표 자료 구성 전문가입니다.
사용자가 제공하는 발표 주제, 대상 청중, 발표 시간을 바탕으로 효과적인 슬라이드 구성과 발표 스크립트를 작성합니다.

작성 규칙:
- 발표 시간에 맞게 슬라이드 수를 조절합니다 (보통 1슬라이드당 1~2분).
- 각 슬라이드에 제목, 핵심 포인트, 발표 스크립트를 포함합니다.
- 청중의 수준과 관심사에 맞게 내용을 조절합니다.
- 도입(주제 소개) → 본론(핵심 내용) → 결론(요약/행동 요청) 구조를 따릅니다.
- 스크립트는 자연스러운 구어체로 작성합니다.

반드시 아래 JSON 형식으로만 응답하세요:
```json
{
  "topic": "발표 주제",
  "audience": "대상 청중",
  "duration_minutes": 15,
  "slides": [
    {
      "slide_number": 1,
      "title": "슬라이드 제목",
      "key_points": ["요점1", "요점2"],
      "script": "발표 스크립트 텍스트"
    }
  ]
}
```
"""


class PresentationHelperInput(BaseModel):
    """Presentation Helper Tool 입력 스키마."""

    topic: str = Field(..., description="발표 주제")
    audience: str = Field(..., description="대상 청중")
    duration_minutes: int = Field(default=15, description="발표 시간 (분)")


class PresentationHelperTool(BaseAgentTool):
    """LLM을 호출하여 발표 자료 구성과 스크립트를 생성하는 Tool."""

    name: str = "presentation_helper"
    description: str = (
        "발표 자료의 슬라이드 구성과 스크립트를 생성합니다. "
        "발표 주제, 대상 청중, 발표 시간을 입력하면 슬라이드별 구성과 스크립트를 반환합니다."
    )
    args_schema: type[BaseModel] = PresentationHelperInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(
        self,
        topic: str,
        audience: str,
        duration_minutes: int = 15,
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("PresentationHelperTool은 비동기 전용입니다. _arun을 사용하세요.")

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="발표 자료 생성 중 오류가 발생했습니다",
    )
    async def _arun(
        self,
        topic: str,
        audience: str,
        duration_minutes: int = 15,
        config: RunnableConfig | None = None,
    ) -> tuple[str, dict]:
        user_input = (
            f"발표 주제: {topic}\n"
            f"대상 청중: {audience}\n"
            f"발표 시간: {duration_minutes}분"
        )

        response_text = await call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_input=user_input,
        )

        parsed = parse_json_response(response_text)

        if parsed and "slides" in parsed:
            detected_topic = parsed.get("topic", topic)
            detected_audience = parsed.get("audience", audience)
            detected_duration = parsed.get("duration_minutes", duration_minutes)
            slides = parsed.get("slides", [])
        else:
            detected_topic = topic
            detected_audience = audience
            detected_duration = duration_minutes
            slides = []

        artifact: dict = {
            "type": AGENT_TYPE,
            "topic": detected_topic,
            "audience": detected_audience,
            "duration_minutes": detected_duration,
            "slides": slides,
        }

        content = self._build_content(
            detected_topic, detected_audience, detected_duration,
            slides, response_text, parsed,
        )
        return content, artifact

    def _build_content(
        self,
        topic: str,
        audience: str,
        duration_minutes: int,
        slides: list,
        response_text: str,
        parsed: dict | None,
    ) -> str:
        """LLM 응답을 사용자 친화적 텍스트로 변환합니다."""
        if not parsed:
            return response_text

        lines = [
            f"발표: {topic}",
            f"청중: {audience} | 시간: {duration_minutes}분",
            f"슬라이드 수: {len(slides)}장",
        ]

        if slides:
            lines.append("")
            for slide in slides:
                num = slide.get("slide_number", 0)
                title = slide.get("title", "")
                key_points = slide.get("key_points", [])
                lines.append(f"[슬라이드 {num}] {title}")
                for point in key_points:
                    lines.append(f"  • {point}")

        return "\n".join(lines)

    def format_content(self, message: ToolMessage) -> ToolMessage:
        """artifact를 마크다운으로 변환하여 LLM에게 전달합니다."""
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if "error_message" in art:
            return message

        topic = art.get("topic", "")
        audience = art.get("audience", "")
        duration_minutes = art.get("duration_minutes", 0)
        slides = art.get("slides", [])

        md_lines = [
            f"## 🎤 발표 자료 구성\n",
            f"**주제:** {topic}\n",
            f"**청중:** {audience} | **시간:** {duration_minutes}분 | **슬라이드:** {len(slides)}장\n",
            "---\n",
        ]

        for slide in slides:
            num = slide.get("slide_number", 0)
            title = slide.get("title", "")
            key_points = slide.get("key_points", [])
            script = slide.get("script", "")

            md_lines.append(f"### 슬라이드 {num}: {title}\n")
            if key_points:
                md_lines.append("**핵심 포인트:**")
                for point in key_points:
                    md_lines.append(f"- {point}")
                md_lines.append("")
            if script:
                md_lines.append(f"**스크립트:**\n> {script}\n")

        md = "\n".join(md_lines)
        return message.model_copy(update={"content": md})
