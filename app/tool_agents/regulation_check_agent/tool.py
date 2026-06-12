"""Regulation Check Agent Tool 구현.

LLM을 호출하여 규정 관련 질문에 대해 관련 조항, 적용 범위,
주의사항을 정리하고 면책조항을 포함합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact
from app.tool_agents._llm_utils import call_llm, parse_json_response

AGENT_TYPE = "regulation_check_agent"

_SYSTEM_PROMPT = """\
당신은 규정 및 컴플라이언스 전문가입니다.
사용자의 규정 관련 질문에 대해 관련 규정 조항, 적용 범위, 주의사항을 정리하여 답변합니다.

답변 규칙:
- 질문과 관련된 규정/법규/내규 조항을 찾아 정리합니다.
- 각 규정의 제목, 조항 번호, 핵심 내용을 명시합니다.
- 실무 적용 시 주의사항을 별도로 정리합니다.
- 반드시 면책조항(disclaimer)을 포함합니다.

카테고리별 중점 영역:
- hr: 근로기준법, 인사규정, 취업규칙, 급여/복리후생 규정
- finance: 회계기준, 세법, 내부회계관리규정, 자금관리규정
- security: 정보보호규정, 개인정보보호법, 보안관리지침
- procurement: 구매규정, 계약규정, 입찰규정
- general: 범용 규정 안내

반드시 아래 JSON 형식으로만 응답하세요:
```json
{
  "query": "원본 질문",
  "regulations": [
    {"title": "규정명", "article": "조항", "content": "내용 요약"}
  ],
  "summary": "요약 답변",
  "cautions": ["주의사항1", "주의사항2"],
  "disclaimer": "본 답변은 일반적인 정보 제공 목적이며, 법률적 조언이 아닙니다. 구체적인 사안은 관련 부서 또는 전문가에게 확인하시기 바랍니다."
}
```
"""


class RegulationCheckInput(BaseModel):
    """Regulation Check Tool 입력 스키마."""

    query: str = Field(..., description="규정 관련 질문")
    category: str = Field(
        default="general",
        description="카테고리 (hr | finance | security | procurement | general)",
    )


class RegulationCheckTool(BaseAgentTool):
    """LLM을 호출하여 규정 관련 질문에 답변하는 Tool."""

    name: str = "regulation_check"
    description: str = (
        "규정 관련 질문에 대해 관련 조항, 적용 범위, 주의사항을 정리하여 답변합니다. "
        "질문과 카테고리를 입력하면 관련 규정과 면책조항을 포함한 답변을 반환합니다."
    )
    args_schema: type[BaseModel] = RegulationCheckInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(
        self,
        query: str,
        category: str = "general",
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("RegulationCheckTool은 비동기 전용입니다. _arun을 사용하세요.")

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="규정 확인 중 오류가 발생했습니다",
    )
    async def _arun(
        self,
        query: str,
        category: str = "general",
        config: RunnableConfig | None = None,
    ) -> tuple[str, dict]:
        user_input = (
            f"카테고리: {category}\n\n"
            f"질문: {query}"
        )

        response_text = await call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_input=user_input,
        )

        parsed = parse_json_response(response_text)

        if parsed and "regulations" in parsed:
            original_query = parsed.get("query", query)
            regulations = parsed.get("regulations", [])
            summary = parsed.get("summary", "")
            cautions = parsed.get("cautions", [])
            disclaimer = parsed.get(
                "disclaimer",
                "본 답변은 일반적인 정보 제공 목적이며, 법률적 조언이 아닙니다.",
            )
        else:
            original_query = query
            regulations = []
            summary = response_text
            cautions = []
            disclaimer = "본 답변은 일반적인 정보 제공 목적이며, 법률적 조언이 아닙니다."

        artifact: dict = {
            "type": AGENT_TYPE,
            "query": original_query,
            "regulations": regulations,
            "summary": summary,
            "cautions": cautions,
            "disclaimer": disclaimer,
        }

        content = self._build_content(
            original_query, regulations, summary,
            cautions, disclaimer, response_text, parsed,
        )
        return content, artifact

    def _build_content(
        self,
        query: str,
        regulations: list,
        summary: str,
        cautions: list,
        disclaimer: str,
        response_text: str,
        parsed: dict | None,
    ) -> str:
        """LLM 응답을 사용자 친화적 텍스트로 변환합니다."""
        if not parsed:
            return response_text

        lines = [f"질문: {query}", f"\n요약: {summary}"]

        if regulations:
            lines.append("\n관련 규정:")
            for i, reg in enumerate(regulations, 1):
                title = reg.get("title", "")
                article = reg.get("article", "")
                content = reg.get("content", "")
                lines.append(f"  {i}. {title} ({article}): {content}")

        if cautions:
            lines.append("\n주의사항:")
            for i, item in enumerate(cautions, 1):
                lines.append(f"  {i}. {item}")

        lines.append(f"\n⚠️ {disclaimer}")
        return "\n".join(lines)

    def format_content(self, message: ToolMessage) -> ToolMessage:
        """artifact를 마크다운으로 변환하여 LLM에게 전달합니다."""
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if "error_message" in art:
            return message

        query = art.get("query", "")
        regulations = art.get("regulations", [])
        summary = art.get("summary", "")
        cautions = art.get("cautions", [])
        disclaimer = art.get("disclaimer", "")

        md_lines = [
            f"## ⚖️ 규정 확인 결과\n",
            f"**질문:** {query}\n",
            "---\n",
            f"### 요약\n\n{summary}\n",
        ]

        if regulations:
            md_lines.append("### 관련 규정\n")
            md_lines.append("| # | 규정명 | 조항 | 내용 |")
            md_lines.append("|---|--------|------|------|")
            for i, reg in enumerate(regulations, 1):
                title = reg.get("title", "")
                article = reg.get("article", "")
                content = reg.get("content", "")
                md_lines.append(f"| {i} | {title} | {article} | {content} |")
            md_lines.append("")

        if cautions:
            md_lines.append("### ⚠️ 주의사항\n")
            for item in cautions:
                md_lines.append(f"- {item}")
            md_lines.append("")

        if disclaimer:
            md_lines.append(f"---\n\n> _{disclaimer}_")

        md = "\n".join(md_lines)
        return message.model_copy(update={"content": md})
