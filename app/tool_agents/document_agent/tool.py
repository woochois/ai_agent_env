"""Document Agent Tool 구현.

기존 document_review, report_outline, presentation_helper 에이전트를
단일 Expert Agent로 통합합니다. sub_command 파라미터를 통해 내부 라우팅합니다.

Sub_Commands:
- review: 문서 검토 (문법, 일관성, 논리적 흐름 분석)
- outline_report: 보고서 개요 생성
- assist_presentation: 발표 자료 슬라이드 구성 생성

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8
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

AGENT_TYPE = "document"

_VALID_COMMANDS = frozenset({"review", "outline_report", "assist_presentation"})

# Required fields per sub_command
_REQUIRED_FIELDS: dict[str, list[str]] = {
    "review": ["document"],
    "outline_report": ["topic", "purpose"],
    "assist_presentation": ["topic", "audience"],
}

# --- System Prompts ---

_REVIEW_SYSTEM_PROMPT = """\
당신은 문서 검토 전문가입니다.
사용자가 제공하는 문서를 분석하여 문법, 일관성, 논리적 흐름, 톤 등의 이슈를 식별하고 개선 제안을 제공합니다.

반드시 아래 JSON 형식으로만 응답하세요:
```json
{
  "issues": [
    {"category": "grammar|consistency|flow|tone", "location": "위치 설명", "description": "이슈 설명"}
  ],
  "suggestions": [
    {"original": "원문 부분", "revised": "수정 제안", "reason": "수정 이유"}
  ],
  "overall_score": 7,
  "doc_type": "문서 유형"
}
```
"""

_OUTLINE_SYSTEM_PROMPT = """\
당신은 보고서 구성 전문가입니다.
사용자가 제공하는 주제, 목적, 대상 독자를 바탕으로 체계적인 보고서 목차와 섹션별 요점을 생성해주세요.

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

_PRESENTATION_SYSTEM_PROMPT = """\
당신은 발표 자료 구성 전문가입니다.
사용자가 제공하는 발표 주제, 대상 청중, 발표 시간을 바탕으로 효과적인 슬라이드 구성과 발표 스크립트를 작성합니다.

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


class DocumentInput(BaseModel):
    """Document Agent 입력 스키마."""

    sub_command: str = Field(
        ..., description="실행할 서브커맨드: review | outline_report | assist_presentation"
    )
    document: str = Field(default="", description="검토할 문서 텍스트 (review용)")
    doc_type: str = Field(default="general", description="문서 유형 (review용)")
    topic: str = Field(default="", description="주제 (outline_report, assist_presentation용)")
    purpose: str = Field(default="", description="목적 (outline_report용)")
    audience: str = Field(default="general", description="대상 독자/청중")
    duration_minutes: int = Field(default=15, description="발표 시간(분) (assist_presentation용)")


class DocumentTool(BaseAgentTool):
    """통합 Document Agent Tool.

    sub_command에 따라 적절한 내부 핸들러로 라우팅합니다.
    """

    name: str = "document"
    description: str = (
        "문서 관련 작업을 수행합니다. review(문서 검토), outline_report(보고서 개요), "
        "assist_presentation(발표 자료 생성)을 지원합니다."
    )
    args_schema: type[BaseModel] = DocumentInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(
        self,
        sub_command: str,
        document: str = "",
        doc_type: str = "general",
        topic: str = "",
        purpose: str = "",
        audience: str = "general",
        duration_minutes: int = 15,
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("비동기(_arun)로만 실행됩니다")

    @auto_error_artifact(agent_type=AGENT_TYPE, default_message="Document Agent 실행 중 오류가 발생했습니다")
    async def _arun(
        self,
        sub_command: str,
        document: str = "",
        doc_type: str = "general",
        topic: str = "",
        purpose: str = "",
        audience: str = "general",
        duration_minutes: int = 15,
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
            document=document,
            topic=topic,
            purpose=purpose,
            audience=audience,
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
            document=document,
            doc_type=doc_type,
            topic=topic,
            purpose=purpose,
            audience=audience,
            duration_minutes=duration_minutes,
        )

    def _validate_inputs(
        self,
        sub_command: str,
        document: str = "",
        topic: str = "",
        purpose: str = "",
        audience: str = "",
    ) -> list[str]:
        """서브커맨드별 필수 입력 필드를 검증합니다."""
        missing = []
        required = _REQUIRED_FIELDS.get(sub_command, [])
        field_values = {
            "document": document,
            "topic": topic,
            "purpose": purpose,
            "audience": audience,
        }
        for field in required:
            val = field_values.get(field, "")
            if not val or not val.strip():
                missing.append(field)
        return missing

    async def _handle_review(self, document: str, doc_type: str = "general", **kwargs: Any) -> tuple[str, dict]:
        """review 서브커맨드: 문서 검토."""
        user_input = f"문서 유형: {doc_type}\n\n검토할 문서:\n{document}"

        try:
            response_text = await call_llm(
                system_prompt=_REVIEW_SYSTEM_PROMPT,
                user_input=user_input,
            )
        except Exception as exc:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message=f"LLM 호출 실패: {exc}",
                sub_command="review",
            )

        parsed = parse_json_response(response_text)

        if parsed and "issues" in parsed:
            return "", build_artifact(
                AGENT_TYPE,
                sub_command="review",
                issues=parsed.get("issues", []),
                suggestions=parsed.get("suggestions", []),
                overall_score=parsed.get("overall_score", 5),
                doc_type=parsed.get("doc_type", doc_type),
            )
        else:
            # JSON 파싱 실패 시 raw text를 content로 사용
            return "", build_artifact(
                AGENT_TYPE,
                sub_command="review",
                content=response_text,
            )

    async def _handle_outline_report(self, topic: str, purpose: str, audience: str = "general", **kwargs: Any) -> tuple[str, dict]:
        """outline_report 서브커맨드: 보고서 개요 생성."""
        user_input = f"주제: {topic}\n목적: {purpose}\n대상 독자: {audience}"

        try:
            response_text = await call_llm(
                system_prompt=_OUTLINE_SYSTEM_PROMPT,
                user_input=user_input,
            )
        except Exception as exc:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message=f"LLM 호출 실패: {exc}",
                sub_command="outline_report",
            )

        parsed = parse_json_response(response_text)

        if parsed and "outline_sections" in parsed:
            return "", build_artifact(
                AGENT_TYPE,
                sub_command="outline_report",
                topic=parsed.get("topic", topic),
                purpose=parsed.get("purpose", purpose),
                outline_sections=parsed.get("outline_sections", []),
            )
        else:
            # JSON 파싱 실패 시 raw text를 content로 사용
            return "", build_artifact(
                AGENT_TYPE,
                sub_command="outline_report",
                content=response_text,
            )

    async def _handle_assist_presentation(self, topic: str, audience: str, duration_minutes: int = 15, **kwargs: Any) -> tuple[str, dict]:
        """assist_presentation 서브커맨드: 발표 자료 슬라이드 구성 생성."""
        user_input = f"발표 주제: {topic}\n대상 청중: {audience}\n발표 시간: {duration_minutes}분"

        try:
            response_text = await call_llm(
                system_prompt=_PRESENTATION_SYSTEM_PROMPT,
                user_input=user_input,
            )
        except Exception as exc:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message=f"LLM 호출 실패: {exc}",
                sub_command="assist_presentation",
            )

        parsed = parse_json_response(response_text)

        if parsed and "slides" in parsed:
            return "", build_artifact(
                AGENT_TYPE,
                sub_command="assist_presentation",
                topic=parsed.get("topic", topic),
                audience=parsed.get("audience", audience),
                duration_minutes=parsed.get("duration_minutes", duration_minutes),
                slides=parsed.get("slides", []),
            )
        else:
            # JSON 파싱 실패 시 raw text를 content로 사용
            return "", build_artifact(
                AGENT_TYPE,
                sub_command="assist_presentation",
                content=response_text,
            )
