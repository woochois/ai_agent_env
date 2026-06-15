"""Communication Agent Tool 구현.

기존 email_draft, translation, meeting_summary 에이전트의
기능을 단일 Tool 클래스에서 sub_command 라우팅을 통해 제공합니다.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact, build_error_artifact
from app.tool_agents._llm_utils import call_llm, parse_json_response

logger = logging.getLogger(__name__)

AGENT_TYPE = "communication"

# ---------------------------------------------------------------------------
# System Prompts (기존 에이전트에서 재사용)
# ---------------------------------------------------------------------------

_EMAIL_SYSTEM_PROMPT = """\
당신은 비즈니스 이메일 작성 전문가입니다.
사용자가 제공하는 목적, 수신자, 핵심 전달 내용을 바탕으로 적절한 비즈니스 이메일 초안을 작성해주세요.

작성 규칙:
- 이메일은 인사말(greeting), 본문(body), 마무리(closing)를 포함해야 합니다.
- 지정된 톤(formal/casual/polite)에 맞는 어투를 사용합니다.
- 지정된 언어(ko: 한국어, en: 영어)로 작성합니다.
- 제목(subject)은 간결하고 명확하게 작성합니다.

반드시 아래 JSON 형식으로만 응답하세요:
```json
{
  "subject": "이메일 제목",
  "body": "인사말을 포함한 이메일 본문 전체"
}
```
"""

_TRANSLATION_SYSTEM_PROMPT = """\
당신은 전문 번역가입니다.
사용자가 제공하는 텍스트를 지정된 목표 언어로 번역해주세요.

번역 규칙:
- 원문의 언어를 자동으로 감지합니다.
- 지정된 도메인(finance/legal/tech/general)의 전문 용어를 정확히 반영합니다.
- 비즈니스 톤을 유지하며 자연스러운 문장으로 번역합니다.
- 원문의 의미와 뉘앙스를 최대한 보존합니다.
- 전문 용어의 일관성을 유지합니다.

반드시 아래 JSON 형식으로만 응답하세요:
```json
{
  "source_text": "원문 텍스트",
  "translated_text": "번역된 텍스트",
  "source_lang": "감지된 원문 언어 코드 (ko 또는 en)",
  "target_lang": "목표 언어 코드"
}
```
"""

_MEETING_SYSTEM_PROMPT = """\
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


# ---------------------------------------------------------------------------
# Required fields per sub_command
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS: dict[str, list[str]] = {
    "draft_email": ["purpose", "recipient", "key_points"],
    "translate": ["text", "target_lang"],
    "summarize_meeting": ["content"],
}


# ---------------------------------------------------------------------------
# Input Schema
# ---------------------------------------------------------------------------


class CommunicationInput(BaseModel):
    """Communication Agent 입력 스키마.

    sub_command에 따라 필요한 필드가 달라집니다:
    - draft_email: purpose, recipient, key_points (필수); tone, language (선택)
    - translate: text, target_lang (필수); domain (선택)
    - summarize_meeting: content (필수); meeting_title (선택)
    """

    sub_command: str = Field(
        ..., description="실행할 서브커맨드: draft_email | translate | summarize_meeting"
    )
    # draft_email fields
    purpose: str = Field(default="", description="이메일 목적 (draft_email용)")
    recipient: str = Field(default="", description="수신자 (draft_email용)")
    key_points: str = Field(default="", description="핵심 전달 내용 (draft_email용)")
    tone: str = Field(default="formal", description="톤 (draft_email용: formal | casual | polite)")
    language: str = Field(default="ko", description="언어 (draft_email용: ko | en)")
    # translate fields
    text: str = Field(default="", description="번역할 원문 (translate용)")
    target_lang: str = Field(default="", description="목표 언어 (translate용)")
    domain: str = Field(default="general", description="도메인 (translate용: finance | legal | tech | general)")
    # summarize_meeting fields
    content: str = Field(default="", description="회의 내용 텍스트 (summarize_meeting용)")
    meeting_title: str = Field(default="", description="회의 제목 (summarize_meeting용, 선택)")


# ---------------------------------------------------------------------------
# Tool Class
# ---------------------------------------------------------------------------


class CommunicationTool(BaseAgentTool):
    """통합 Communication Tool.

    sub_command 파라미터를 통해 draft_email, translate, summarize_meeting
    기능을 단일 진입점으로 제공합니다.
    """

    name: str = "communication"
    description: str = (
        "커뮤니케이션 관련 작업을 통합 제공합니다: 이메일 초안, 번역, 회의록 요약. "
        "sub_command로 기능을 선택합니다."
    )
    args_schema: type[BaseModel] = CommunicationInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    _VALID_COMMANDS: set[str] = {"draft_email", "translate", "summarize_meeting"}

    def _run(
        self,
        sub_command: str,
        **kwargs: Any,
    ):
        raise NotImplementedError("CommunicationTool은 비동기 전용입니다. _arun을 사용하세요.")

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="Communication Agent 실행 중 오류가 발생했습니다",
    )
    async def _arun(
        self,
        sub_command: str,
        purpose: str = "",
        recipient: str = "",
        key_points: str = "",
        tone: str = "formal",
        language: str = "ko",
        text: str = "",
        target_lang: str = "",
        domain: str = "general",
        content: str = "",
        meeting_title: str = "",
        config: RunnableConfig | None = None,
    ) -> tuple[str, dict]:
        """비동기 실행 - 모든 sub_command를 지원합니다."""
        # Sub_command validation
        if sub_command not in self._VALID_COMMANDS:
            return self._invalid_sub_command(sub_command)

        # Required fields validation
        kwargs_map: dict[str, Any] = {
            "purpose": purpose,
            "recipient": recipient,
            "key_points": key_points,
            "tone": tone,
            "language": language,
            "text": text,
            "target_lang": target_lang,
            "domain": domain,
            "content": content,
            "meeting_title": meeting_title,
        }
        missing = self._validate_required_fields(sub_command, kwargs_map)
        if missing:
            return "", build_error_artifact(
                AGENT_TYPE,
                error_message=f"필수 필드가 누락되었습니다: {missing}",
                error_detail=f"sub_command '{sub_command}'에 필요한 필드: {_REQUIRED_FIELDS[sub_command]}",
                sub_command=sub_command,
                missing_fields=missing,
            )

        # Route to handler
        if sub_command == "draft_email":
            return await self._handle_draft_email(
                purpose=purpose,
                recipient=recipient,
                key_points=key_points,
                tone=tone,
                language=language,
            )
        elif sub_command == "translate":
            return await self._handle_translate(
                text=text,
                target_lang=target_lang,
                domain=domain,
            )
        elif sub_command == "summarize_meeting":
            return await self._handle_summarize_meeting(
                content=content,
                meeting_title=meeting_title,
            )

        # Should not reach here
        return self._invalid_sub_command(sub_command)  # pragma: no cover

    # ---------------------------------------------------------------------------
    # Sub_command handlers
    # ---------------------------------------------------------------------------

    async def _handle_draft_email(
        self,
        purpose: str,
        recipient: str,
        key_points: str,
        tone: str = "formal",
        language: str = "ko",
    ) -> tuple[str, dict]:
        """이메일 초안 생성. Requirements: 3.2"""
        user_input = (
            f"목적: {purpose}\n"
            f"수신자: {recipient}\n"
            f"핵심 전달 내용: {key_points}\n"
            f"톤: {tone}\n"
            f"언어: {language}"
        )

        response_text = await self._invoke_llm_with_retry(
            system_prompt=_EMAIL_SYSTEM_PROMPT,
            user_input=user_input,
            sub_command="draft_email",
        )
        if response_text is None:
            # Error artifact already returned by _invoke_llm_with_retry is not used here;
            # this path means we return the error from the except block
            # Actually _invoke_llm_with_retry returns str or raises
            pass  # pragma: no cover

        parsed = parse_json_response(response_text)

        if parsed is not None and "subject" in parsed and "body" in parsed:
            artifact = build_artifact(
                AGENT_TYPE,
                sub_command="draft_email",
                subject=parsed["subject"],
                body=parsed["body"],
            )
            content_str = f"제목: {parsed['subject']}\n\n{parsed['body']}"
        else:
            # JSON parse fallback: raw text as content
            artifact = build_artifact(
                AGENT_TYPE,
                sub_command="draft_email",
                content=response_text,
            )
            content_str = response_text

        return content_str, artifact

    async def _handle_translate(
        self,
        text: str,
        target_lang: str,
        domain: str = "general",
    ) -> tuple[str, dict]:
        """번역 처리. Requirements: 3.3"""
        user_input = (
            f"번역할 텍스트: {text}\n"
            f"목표 언어: {target_lang}\n"
            f"도메인: {domain}"
        )

        response_text = await self._invoke_llm_with_retry(
            system_prompt=_TRANSLATION_SYSTEM_PROMPT,
            user_input=user_input,
            sub_command="translate",
        )

        parsed = parse_json_response(response_text)

        if parsed is not None and "translated_text" in parsed:
            artifact = build_artifact(
                AGENT_TYPE,
                sub_command="translate",
                source_text=parsed.get("source_text", text),
                translated_text=parsed["translated_text"],
                source_lang=parsed.get("source_lang", "unknown"),
                target_lang=parsed.get("target_lang", target_lang),
            )
            content_str = f"[{artifact['source_lang']} → {artifact['target_lang']}] {artifact['translated_text']}"
        else:
            # JSON parse fallback: raw text as content
            artifact = build_artifact(
                AGENT_TYPE,
                sub_command="translate",
                content=response_text,
            )
            content_str = response_text

        return content_str, artifact

    async def _handle_summarize_meeting(
        self,
        content: str,
        meeting_title: str = "",
    ) -> tuple[str, dict]:
        """회의록 요약 생성. Requirements: 3.4"""
        user_input = ""
        if meeting_title:
            user_input += f"회의 제목: {meeting_title}\n\n"
        user_input += f"회의 내용:\n{content}"

        response_text = await self._invoke_llm_with_retry(
            system_prompt=_MEETING_SYSTEM_PROMPT,
            user_input=user_input,
            sub_command="summarize_meeting",
        )

        parsed = parse_json_response(response_text)

        if parsed is not None and "title" in parsed:
            artifact = build_artifact(
                AGENT_TYPE,
                sub_command="summarize_meeting",
                title=parsed["title"],
                attendees=parsed.get("attendees", []),
                agenda=parsed.get("agenda", []),
                decisions=parsed.get("decisions", []),
                action_items=parsed.get("action_items", []),
            )
            content_str = self._build_meeting_markdown(artifact)
        else:
            # JSON parse fallback: raw text as content
            artifact = build_artifact(
                AGENT_TYPE,
                sub_command="summarize_meeting",
                content=response_text,
            )
            content_str = response_text

        return content_str, artifact

    # ---------------------------------------------------------------------------
    # Shared LLM invocation with retry (Requirements: 3.5, 3.6)
    # ---------------------------------------------------------------------------

    async def _invoke_llm_with_retry(
        self,
        system_prompt: str,
        user_input: str,
        sub_command: str,
    ) -> str:
        """call_llm을 호출하고 실패 시 1회 재시도합니다.

        두 번째 실패 시에도 예외를 raise하여 auto_error_artifact가 처리하도록 합니다.
        단, 재시도 실패 시 명확한 에러 메시지를 포함합니다.

        Requirements: 3.6
        """
        try:
            return await call_llm(
                system_prompt=system_prompt,
                user_input=user_input,
            )
        except Exception as first_error:
            logger.warning(
                "Communication Agent '%s' LLM 호출 1차 실패, 재시도합니다: %s",
                sub_command,
                first_error,
            )
            try:
                return await call_llm(
                    system_prompt=system_prompt,
                    user_input=user_input,
                )
            except Exception as second_error:
                logger.error(
                    "Communication Agent '%s' LLM 호출 2차 실패: %s",
                    sub_command,
                    second_error,
                )
                raise RuntimeError(
                    f"LLM 호출이 재시도 후에도 실패했습니다 (sub_command: {sub_command}): {second_error}"
                ) from second_error

    # ---------------------------------------------------------------------------
    # Validation helpers
    # ---------------------------------------------------------------------------

    def _invalid_sub_command(self, sub_command: str) -> tuple[str, dict]:
        """알 수 없는 sub_command에 대한 에러 아티팩트를 반환합니다."""
        return "", build_error_artifact(
            AGENT_TYPE,
            error_message=f"알 수 없는 sub_command입니다: '{sub_command}'",
            error_detail=f"유효한 sub_command: {sorted(self._VALID_COMMANDS)}",
            requested_sub_command=sub_command,
            valid_sub_commands=sorted(self._VALID_COMMANDS),
        )

    def _validate_required_fields(
        self, sub_command: str, kwargs: dict[str, Any]
    ) -> list[str]:
        """sub_command에 필요한 필수 필드가 존재하고 비어있지 않은지 검증합니다.

        Returns:
            누락된 필드 이름 리스트 (비어 있으면 검증 통과).
        """
        required = _REQUIRED_FIELDS.get(sub_command, [])
        missing = []
        for field in required:
            value = kwargs.get(field, "")
            if not value or (isinstance(value, str) and not value.strip()):
                missing.append(field)
        return missing

    # ---------------------------------------------------------------------------
    # Formatting helpers
    # ---------------------------------------------------------------------------

    def _build_meeting_markdown(self, artifact: dict) -> str:
        """회의록 artifact를 마크다운 형식으로 변환합니다."""
        lines = [f"## 📋 {artifact.get('title', '회의록')}\n"]

        attendees = artifact.get("attendees", [])
        if attendees:
            lines.append("### 참석자")
            lines.append(", ".join(attendees))
            lines.append("")

        agenda = artifact.get("agenda", [])
        if agenda:
            lines.append("### 안건")
            for item in agenda:
                lines.append(f"- {item}")
            lines.append("")

        decisions = artifact.get("decisions", [])
        if decisions:
            lines.append("### 결정사항")
            for item in decisions:
                lines.append(f"- {item}")
            lines.append("")

        action_items = artifact.get("action_items", [])
        if action_items:
            lines.append("### 액션아이템")
            for item in action_items:
                assignee = item.get("assignee", "미지정")
                task = item.get("task", "")
                deadline = item.get("deadline", "미정")
                lines.append(f"- **{assignee}**: {task} (마감: {deadline})")
            lines.append("")

        return "\n".join(lines)

    def format_content(self, message: ToolMessage) -> ToolMessage:
        """artifact를 LLM 전달용 텍스트로 변환합니다."""
        art = message.artifact if isinstance(message.artifact, dict) else {}

        # 에러 아티팩트
        if "error_message" in art:
            return message.model_copy(update={"content": art["error_message"]})

        sub_cmd = art.get("sub_command", "")

        if sub_cmd == "draft_email":
            subject = art.get("subject", "")
            body = art.get("body", art.get("content", ""))
            md = f"## ✉️ 이메일 초안\n\n**제목:** {subject}\n\n---\n\n{body}"
            return message.model_copy(update={"content": md})

        elif sub_cmd == "translate":
            translated = art.get("translated_text", art.get("content", ""))
            source_lang = art.get("source_lang", "")
            target_lang = art.get("target_lang", "")
            md = f"## 🌐 번역 결과\n\n**방향:** {source_lang} → {target_lang}\n\n{translated}"
            return message.model_copy(update={"content": md})

        elif sub_cmd == "summarize_meeting":
            if "title" in art:
                md = self._build_meeting_markdown(art)
            else:
                md = art.get("content", "")
            return message.model_copy(update={"content": md})

        return message
