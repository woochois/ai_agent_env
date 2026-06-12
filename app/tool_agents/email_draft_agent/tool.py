"""Email Draft Agent Tool 구현.

LLM을 호출하여 비즈니스 이메일 초안을 생성합니다. 목적, 수신자, 핵심내용,
톤(formal/casual/polite), 언어(ko/en)를 입력받아 구조화된 이메일을 작성합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact

from app.tool_agents._llm_utils import call_llm, parse_json_response

AGENT_TYPE = "email_draft_agent"

_SYSTEM_PROMPT = """\
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


class EmailDraftInput(BaseModel):
    """Email Draft Tool 입력 스키마."""

    purpose: str = Field(..., description="이메일 목적")
    recipient: str = Field(..., description="수신자 (이름/직함)")
    key_points: str = Field(..., description="핵심 전달 내용")
    tone: str = Field(default="formal", description="톤 (formal | casual | polite)")
    language: str = Field(default="ko", description="언어 (ko | en)")


class EmailDraftTool(BaseAgentTool):
    """LLM을 호출하여 비즈니스 이메일 초안을 생성하는 Tool."""

    name: str = "email_draft"
    description: str = (
        "비즈니스 이메일 초안을 작성합니다. "
        "목적, 수신자, 핵심 전달 내용을 입력하면 적절한 톤과 구조의 이메일을 생성합니다."
    )
    args_schema: type[BaseModel] = EmailDraftInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(
        self,
        purpose: str,
        recipient: str,
        key_points: str,
        tone: str = "formal",
        language: str = "ko",
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("EmailDraftTool은 비동기 전용입니다. _arun을 사용하세요.")

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="이메일 초안 생성 중 오류가 발생했습니다",
    )
    async def _arun(
        self,
        purpose: str,
        recipient: str,
        key_points: str,
        tone: str = "formal",
        language: str = "ko",
        config: RunnableConfig | None = None,
    ) -> tuple[str, dict]:
        user_input = (
            f"목적: {purpose}\n"
            f"수신자: {recipient}\n"
            f"핵심 전달 내용: {key_points}\n"
            f"톤: {tone}\n"
            f"언어: {language}"
        )

        response_text = await call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_input=user_input,
        )

        parsed = parse_json_response(response_text)

        if parsed and "subject" in parsed and "body" in parsed:
            subject = parsed["subject"]
            body = parsed["body"]
        else:
            # JSON 파싱 실패 시 응답 전체를 body로 사용
            subject = f"[{purpose}] {recipient}님께"
            body = response_text

        artifact: dict = {
            "type": AGENT_TYPE,
            "subject": subject,
            "body": body,
            "tone": tone,
            "language": language,
        }

        content = f"제목: {subject}\n\n{body}"
        return content, artifact

    def format_content(self, message: ToolMessage) -> ToolMessage:
        """artifact를 마크다운으로 변환하여 LLM에게 전달합니다."""
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if "error_message" in art:
            return message

        subject = art.get("subject", "")
        body = art.get("body", "")
        tone = art.get("tone", "")
        language = art.get("language", "")

        md = (
            f"## ✉️ 이메일 초안\n\n"
            f"**제목:** {subject}\n\n"
            f"**톤:** {tone} | **언어:** {language}\n\n"
            f"---\n\n"
            f"{body}"
        )
        return message.model_copy(update={"content": md})
