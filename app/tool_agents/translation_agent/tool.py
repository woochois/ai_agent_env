"""Translation Agent Tool 구현.

LLM을 호출하여 비즈니스 문서를 한↔영 번역합니다. 원문 언어를 자동 감지하고
도메인(finance/legal/tech/general) 전문 용어를 반영하여 비즈니스 톤을 유지합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact
from app.tool_agents._llm_utils import call_llm, parse_json_response

AGENT_TYPE = "translation_agent"

_SYSTEM_PROMPT = """\
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
  "target_lang": "목표 언어 코드",
  "domain": "도메인"
}
```
"""


class TranslationInput(BaseModel):
    """Translation Tool 입력 스키마."""

    text: str = Field(..., description="번역할 원문")
    target_lang: str = Field(..., description="목표 언어 (ko | en)")
    domain: str = Field(default="general", description="도메인 (finance | legal | tech | general)")


class TranslationTool(BaseAgentTool):
    """LLM을 호출하여 비즈니스 문서를 한↔영 번역하는 Tool."""

    name: str = "translation"
    description: str = (
        "비즈니스 문서를 한↔영 번역합니다. "
        "원문 언어를 자동 감지하고 도메인 전문 용어를 반영하여 비즈니스 톤을 유지합니다."
    )
    args_schema: type[BaseModel] = TranslationInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(
        self,
        text: str,
        target_lang: str,
        domain: str = "general",
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("TranslationTool은 비동기 전용입니다. _arun을 사용하세요.")

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="번역 실행 중 오류가 발생했습니다",
    )
    async def _arun(
        self,
        text: str,
        target_lang: str,
        domain: str = "general",
        config: RunnableConfig | None = None,
    ) -> tuple[str, dict]:
        user_input = (
            f"번역할 텍스트: {text}\n"
            f"목표 언어: {target_lang}\n"
            f"도메인: {domain}"
        )

        response_text = await call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_input=user_input,
        )

        parsed = parse_json_response(response_text)

        if parsed and "translated_text" in parsed:
            source_text = parsed.get("source_text", text)
            translated_text = parsed["translated_text"]
            source_lang = parsed.get("source_lang", "unknown")
            target_lang_result = parsed.get("target_lang", target_lang)
            domain_result = parsed.get("domain", domain)
        else:
            # JSON 파싱 실패 시 응답 전체를 번역문으로 사용
            source_text = text
            translated_text = response_text
            source_lang = "unknown"
            target_lang_result = target_lang
            domain_result = domain

        artifact: dict = {
            "type": AGENT_TYPE,
            "source_text": source_text,
            "translated_text": translated_text,
            "source_lang": source_lang,
            "target_lang": target_lang_result,
            "domain": domain_result,
        }

        content = f"[{source_lang} → {target_lang_result}] {translated_text}"
        return content, artifact

    def format_content(self, message: ToolMessage) -> ToolMessage:
        """artifact를 마크다운으로 변환하여 LLM에게 전달합니다."""
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if "error_message" in art:
            return message

        source_text = art.get("source_text", "")
        translated_text = art.get("translated_text", "")
        source_lang = art.get("source_lang", "")
        target_lang = art.get("target_lang", "")
        domain = art.get("domain", "")

        md = (
            f"## 🌐 번역 결과\n\n"
            f"**방향:** {source_lang} → {target_lang} | **도메인:** {domain}\n\n"
            f"---\n\n"
            f"**원문:**\n\n{source_text}\n\n"
            f"**번역문:**\n\n{translated_text}"
        )
        return message.model_copy(update={"content": md})
