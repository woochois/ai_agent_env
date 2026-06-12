"""Data Insight Agent Tool 구현.

LLM을 호출하여 데이터의 패턴, 이상치, 트렌드를 분석하고
인사이트와 권장 조치를 도출합니다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact
from app.tool_agents._llm_utils import call_llm, parse_json_response

AGENT_TYPE = "data_insight_agent"

_SYSTEM_PROMPT = """\
당신은 데이터 분석 전문가입니다.
사용자가 제공하는 데이터를 분석하여 패턴, 이상치, 트렌드를 식별하고 실행 가능한 인사이트를 도출합니다.

분석 관점:
- sales: 매출, 판매량, 고객 구매 패턴 중심 분석
- cost: 비용 구조, 절감 기회, 예산 대비 실적 분석
- hr: 인력 현황, 이직률, 생산성 지표 분석
- customer: 고객 행동, 만족도, 이탈률 분석
- general: 범용 데이터 분석

분석 결과에는 다음을 포함합니다:
- insights: 핵심 발견 사항
- trends: 데이터에서 관찰되는 트렌드
- anomalies: 이상치나 비정상 패턴
- recommendations: 데이터 기반 권장 조치

반드시 아래 JSON 형식으로만 응답하세요:
```json
{
  "insights": ["핵심 발견1", "핵심 발견2"],
  "trends": ["트렌드1 설명", "트렌드2 설명"],
  "anomalies": ["이상치1 설명"],
  "recommendations": ["권장 조치1", "권장 조치2"],
  "perspective": "분석 관점"
}
```
"""


class DataInsightInput(BaseModel):
    """Data Insight Tool 입력 스키마."""

    data: str = Field(..., description="분석할 데이터 (CSV, 마크다운 테이블 등)")
    perspective: str = Field(
        default="general",
        description="분석 관점 (sales | cost | hr | customer | general)",
    )


class DataInsightTool(BaseAgentTool):
    """LLM을 호출하여 데이터를 분석하고 인사이트를 도출하는 Tool."""

    name: str = "data_insight"
    description: str = (
        "데이터를 분석하여 패턴, 이상치, 트렌드를 식별하고 인사이트를 도출합니다. "
        "CSV나 테이블 형식 데이터와 분석 관점을 입력하면 구조화된 분석 결과를 반환합니다."
    )
    args_schema: type[BaseModel] = DataInsightInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(
        self,
        data: str,
        perspective: str = "general",
        config: RunnableConfig | None = None,
    ):
        raise NotImplementedError("DataInsightTool은 비동기 전용입니다. _arun을 사용하세요.")

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="데이터 인사이트 분석 중 오류가 발생했습니다",
    )
    async def _arun(
        self,
        data: str,
        perspective: str = "general",
        config: RunnableConfig | None = None,
    ) -> tuple[str, dict]:
        user_input = (
            f"분석 관점: {perspective}\n\n"
            f"분석할 데이터:\n{data}"
        )

        response_text = await call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_input=user_input,
        )

        parsed = parse_json_response(response_text)

        if parsed and "insights" in parsed:
            insights = parsed.get("insights", [])
            trends = parsed.get("trends", [])
            anomalies = parsed.get("anomalies", [])
            recommendations = parsed.get("recommendations", [])
            detected_perspective = parsed.get("perspective", perspective)
        else:
            insights = []
            trends = []
            anomalies = []
            recommendations = []
            detected_perspective = perspective

        artifact: dict = {
            "type": AGENT_TYPE,
            "insights": insights,
            "trends": trends,
            "anomalies": anomalies,
            "recommendations": recommendations,
            "perspective": detected_perspective,
        }

        content = self._build_content(
            insights, trends, anomalies, recommendations,
            detected_perspective, response_text, parsed,
        )
        return content, artifact

    def _build_content(
        self,
        insights: list,
        trends: list,
        anomalies: list,
        recommendations: list,
        perspective: str,
        response_text: str,
        parsed: dict | None,
    ) -> str:
        """LLM 응답을 사용자 친화적 텍스트로 변환합니다."""
        if not parsed:
            return response_text

        lines = [f"데이터 분석 결과 (관점: {perspective})"]

        if insights:
            lines.append("\n핵심 인사이트:")
            for i, item in enumerate(insights, 1):
                lines.append(f"  {i}. {item}")

        if trends:
            lines.append("\n트렌드:")
            for i, item in enumerate(trends, 1):
                lines.append(f"  {i}. {item}")

        if anomalies:
            lines.append("\n이상치:")
            for i, item in enumerate(anomalies, 1):
                lines.append(f"  {i}. {item}")

        if recommendations:
            lines.append("\n권장 조치:")
            for i, item in enumerate(recommendations, 1):
                lines.append(f"  {i}. {item}")

        return "\n".join(lines)

    def format_content(self, message: ToolMessage) -> ToolMessage:
        """artifact를 마크다운으로 변환하여 LLM에게 전달합니다."""
        art = message.artifact if isinstance(message.artifact, dict) else {}
        if "error_message" in art:
            return message

        insights = art.get("insights", [])
        trends = art.get("trends", [])
        anomalies = art.get("anomalies", [])
        recommendations = art.get("recommendations", [])
        perspective = art.get("perspective", "general")

        md_lines = [
            f"## 📊 데이터 인사이트\n",
            f"**분석 관점:** {perspective}\n",
            "---\n",
        ]

        if insights:
            md_lines.append("### 핵심 인사이트\n")
            for i, item in enumerate(insights, 1):
                md_lines.append(f"{i}. {item}")
            md_lines.append("")

        if trends:
            md_lines.append("### 트렌드\n")
            for i, item in enumerate(trends, 1):
                md_lines.append(f"{i}. {item}")
            md_lines.append("")

        if anomalies:
            md_lines.append("### 이상치\n")
            for i, item in enumerate(anomalies, 1):
                md_lines.append(f"⚠️ {item}")
            md_lines.append("")

        if recommendations:
            md_lines.append("### 권장 조치\n")
            for i, item in enumerate(recommendations, 1):
                md_lines.append(f"- {item}")
            md_lines.append("")

        md = "\n".join(md_lines)
        return message.model_copy(update={"content": md})
