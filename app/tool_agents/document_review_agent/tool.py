"""Document Review Agent Tool 구현.

LLM을 호출하여 문서의 문법, 일관성, 논리적 흐름을 분석하고
개선 제안을 제공합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact
from app.tool_agents._llm_utils import call_llm, parse_json_response

AGENT_TYPE = "document_review_agent"

_SYSTEM_PROMPT = """\
당신은 문서 검토 전문가입니다.
사용자가 제공하는 문서를 분석하여 문법, 일관성, 논리적 흐름, 톤 등의 이슈를 식별하고 개선 제안을 제공합니다.

검토 기준:
- grammar: 맞춤법, 문법, 띄어쓰기 오류
- consistency: 용어, 표현, 형식의 일관성
- flow: 문단 간 논리적 연결, 전개 흐름
- tone: 문서 유형에 맞는 어조와 격식

문서 유형별 관례:
- report: 객관적이고 간결한 표현, 데이터 기반 서술
- proposal: 설득력 있는 논리 전개, 명확한 목적 제시
- email: 간결하고 예의 바른 표현, 명확한 요청사항
- contract: 법률 용어의 정확성, 모호하지 않은 표현
- general: 일반적인 문서 작성 규칙 적용

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

overall_score는 1~10 사이의 정수로, 문서의 전반적인 품질을 평가합니다.
"""


class DocumentReviewInput(BaseModel):
    """Document Review Tool 입력 스키마."""

    document: str = Field(..., description="검토할 문서 텍스트")
    doc_type: str = Field(
        default="general",
        description="문서 유형 (report | proposal | email | contract | general)",
    )


class DocumentReviewTool(BaseAgentTool):
    """LLM을 호출하여 문서를 검토하고 개선 제안을 제공하는 Tool."""

    name: str = "document_review"
    description: str = (
        "작성한 문서의 문법, 일관성, 논리적 흐름을 검토하고 개선 제안을 제공합니다. "
        "문서 텍스트와 문서 유형을 입력하면 이슈 목록, 수정 제안, 전체 점수를 반환합니다."
    )
    args_schema: type[BaseModel] = DocumentReviewInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(
        self,
        document: str,
        doc_type: str = "general",
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("DocumentReviewTool은 비동기 전용입니다. _arun을 사용하세요.")

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="문서 검토 중 오류가 발생했습니다",
    )
    async def _arun(
        self,
        document: str,
        doc_type: str = "general",
        config: RunnableConfig | None = None,
    ) -> tuple[str, dict]:
        user_input = (
            f"문서 유형: {doc_type}\n\n"
            f"검토할 문서:\n{document}"
        )

        response_text = await call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_input=user_input,
        )

        parsed = parse_json_response(response_text)

        if parsed and "issues" in parsed:
            issues = parsed.get("issues", [])
            suggestions = parsed.get("suggestions", [])
            overall_score = parsed.get("overall_score", 5)
            detected_doc_type = parsed.get("doc_type", doc_type)
        else:
            # JSON 파싱 실패 시 기본 응답 구성
            issues = []
            suggestions = []
            overall_score = 5
            detected_doc_type = doc_type

        artifact: dict = {
            "type": AGENT_TYPE,
            "issues": issues,
            "suggestions": suggestions,
            "overall_score": overall_score,
            "doc_type": detected_doc_type,
        }

        content = self._build_content(issues, suggestions, overall_score, detected_doc_type, response_text, parsed)
        return content, artifact

    def _build_content(
        self,
        issues: list,
        suggestions: list,
        overall_score: int,
        doc_type: str,
        response_text: str,
        parsed: dict | None,
    ) -> str:
        """LLM 응답을 사용자 친화적 텍스트로 변환합니다."""
        if not parsed:
            return response_text

        lines = [f"문서 검토 결과 (유형: {doc_type}, 점수: {overall_score}/10)"]

        if issues:
            lines.append("\n발견된 이슈:")
            for i, issue in enumerate(issues, 1):
                category = issue.get("category", "")
                location = issue.get("location", "")
                desc = issue.get("description", "")
                lines.append(f"  {i}. [{category}] {location} - {desc}")

        if suggestions:
            lines.append("\n개선 제안:")
            for i, sug in enumerate(suggestions, 1):
                original = sug.get("original", "")
                revised = sug.get("revised", "")
                reason = sug.get("reason", "")
                lines.append(f"  {i}. \"{original}\" → \"{revised}\" ({reason})")

        return "\n".join(lines)

    def format_content(self, message: ToolMessage) -> ToolMessage:
        """artifact를 마크다운으로 변환하여 LLM에게 전달합니다."""
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if "error_message" in art:
            return message

        issues = art.get("issues", [])
        suggestions = art.get("suggestions", [])
        overall_score = art.get("overall_score", 0)
        doc_type = art.get("doc_type", "general")

        md_lines = [
            f"## 📝 문서 검토 결과\n",
            f"**문서 유형:** {doc_type} | **전체 점수:** {overall_score}/10\n",
            "---\n",
        ]

        if issues:
            md_lines.append("### 발견된 이슈\n")
            md_lines.append("| # | 카테고리 | 위치 | 설명 |")
            md_lines.append("|---|----------|------|------|")
            for i, issue in enumerate(issues, 1):
                category = issue.get("category", "")
                location = issue.get("location", "")
                desc = issue.get("description", "")
                md_lines.append(f"| {i} | {category} | {location} | {desc} |")
            md_lines.append("")

        if suggestions:
            md_lines.append("### 개선 제안\n")
            for i, sug in enumerate(suggestions, 1):
                original = sug.get("original", "")
                revised = sug.get("revised", "")
                reason = sug.get("reason", "")
                md_lines.append(f"**{i}.** \"{original}\"")
                md_lines.append(f"  → \"{revised}\"")
                md_lines.append(f"  _({reason})_\n")

        md = "\n".join(md_lines)
        return message.model_copy(update={"content": md})
