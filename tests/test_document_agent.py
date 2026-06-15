"""Document Agent 단위 테스트.

sub_command 라우팅, 입력 검증, LLM 호출 에러 처리를 검증합니다.

Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.tool_agents.document_agent.tool import DocumentTool


@pytest.fixture
def tool():
    """DocumentTool 인스턴스를 생성합니다."""
    return DocumentTool()


# ---------------------------------------------------------------------------
# Sub_command validation
# ---------------------------------------------------------------------------


class TestSubCommandValidation:
    """sub_command 검증 테스트."""

    @pytest.mark.asyncio
    async def test_unknown_sub_command_returns_error(self, tool: DocumentTool):
        """알 수 없는 sub_command는 에러 아티팩트를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="unknown")
        assert artifact["type"] == "document"
        assert "error_message" in artifact
        assert "unknown" in artifact["error_message"]

    @pytest.mark.asyncio
    async def test_unknown_sub_command_includes_valid_list(self, tool: DocumentTool):
        """에러 아티팩트에 유효한 sub_command 목록이 포함되어야 합니다."""
        _, artifact = await tool._arun(sub_command="bad_cmd")
        assert "valid_commands" in artifact
        valid = artifact["valid_commands"]
        assert "review" in valid
        assert "outline_report" in valid
        assert "assist_presentation" in valid


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestInputValidation:
    """입력 검증 테스트. Requirements: 4.5"""

    @pytest.mark.asyncio
    async def test_review_missing_document(self, tool: DocumentTool):
        """review에서 document가 비어있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="review", document="")
        assert "error_message" in artifact
        assert "document" in str(artifact.get("missing_fields", []))

    @pytest.mark.asyncio
    async def test_review_whitespace_document(self, tool: DocumentTool):
        """review에서 document가 공백만 있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="review", document="   ")
        assert "error_message" in artifact

    @pytest.mark.asyncio
    async def test_outline_report_missing_topic(self, tool: DocumentTool):
        """outline_report에서 topic이 비어있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="outline_report", topic="", purpose="test")
        assert "error_message" in artifact
        assert "topic" in str(artifact.get("missing_fields", []))

    @pytest.mark.asyncio
    async def test_outline_report_missing_purpose(self, tool: DocumentTool):
        """outline_report에서 purpose가 비어있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="outline_report", topic="AI", purpose="")
        assert "error_message" in artifact
        assert "purpose" in str(artifact.get("missing_fields", []))

    @pytest.mark.asyncio
    async def test_assist_presentation_missing_topic(self, tool: DocumentTool):
        """assist_presentation에서 topic이 비어있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="assist_presentation", topic="", audience="developers")
        assert "error_message" in artifact
        assert "topic" in str(artifact.get("missing_fields", []))

    @pytest.mark.asyncio
    async def test_assist_presentation_missing_audience(self, tool: DocumentTool):
        """assist_presentation에서 audience가 비어있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="assist_presentation", topic="AI", audience="")
        assert "error_message" in artifact
        assert "audience" in str(artifact.get("missing_fields", []))


# ---------------------------------------------------------------------------
# Sub_command routing with mocked LLM
# ---------------------------------------------------------------------------


class TestReviewSubCommand:
    """review sub_command 테스트 (LLM mocked)."""

    @pytest.mark.asyncio
    async def test_review_returns_issues_artifact(self, tool: DocumentTool):
        """review는 issues 리스트를 포함하는 artifact를 반환해야 합니다."""
        mock_response = json.dumps({
            "issues": [{"category": "grammar", "location": "1문단", "description": "오타"}],
            "suggestions": [{"original": "테스트", "revised": "테스트!", "reason": "강조"}],
            "overall_score": 7,
            "doc_type": "general",
        })

        with patch("app.tool_agents.document_agent.tool.call_llm", new_callable=AsyncMock, return_value=mock_response):
            _, artifact = await tool._arun(sub_command="review", document="테스트 문서입니다.")

        assert artifact["type"] == "document"
        assert artifact["sub_command"] == "review"
        assert "issues" in artifact
        assert isinstance(artifact["issues"], list)
        assert artifact["overall_score"] == 7

    @pytest.mark.asyncio
    async def test_review_json_parse_failure_returns_raw_content(self, tool: DocumentTool):
        """JSON 파싱 실패 시 raw text를 content로 반환해야 합니다. Requirements: 4.7"""
        raw_text = "이 문서는 전반적으로 양호합니다."

        with patch("app.tool_agents.document_agent.tool.call_llm", new_callable=AsyncMock, return_value=raw_text):
            _, artifact = await tool._arun(sub_command="review", document="테스트 문서")

        assert artifact["type"] == "document"
        assert artifact.get("content") == raw_text


class TestOutlineReportSubCommand:
    """outline_report sub_command 테스트 (LLM mocked)."""

    @pytest.mark.asyncio
    async def test_outline_report_returns_sections(self, tool: DocumentTool):
        """outline_report는 outline_sections를 포함하는 artifact를 반환해야 합니다."""
        mock_response = json.dumps({
            "topic": "AI 기술",
            "purpose": "동향 분석",
            "outline_sections": [
                {"title": "서론", "key_points": ["배경"], "subsections": []},
            ],
        })

        with patch("app.tool_agents.document_agent.tool.call_llm", new_callable=AsyncMock, return_value=mock_response):
            _, artifact = await tool._arun(
                sub_command="outline_report", topic="AI 기술", purpose="동향 분석"
            )

        assert artifact["type"] == "document"
        assert artifact["sub_command"] == "outline_report"
        assert "outline_sections" in artifact
        assert isinstance(artifact["outline_sections"], list)


class TestAssistPresentationSubCommand:
    """assist_presentation sub_command 테스트 (LLM mocked)."""

    @pytest.mark.asyncio
    async def test_assist_presentation_returns_slides(self, tool: DocumentTool):
        """assist_presentation은 slides를 포함하는 artifact를 반환해야 합니다."""
        mock_response = json.dumps({
            "topic": "ML 소개",
            "audience": "개발자",
            "duration_minutes": 20,
            "slides": [
                {"slide_number": 1, "title": "소개", "key_points": ["AI란?"], "script": "안녕하세요"},
            ],
        })

        with patch("app.tool_agents.document_agent.tool.call_llm", new_callable=AsyncMock, return_value=mock_response):
            _, artifact = await tool._arun(
                sub_command="assist_presentation", topic="ML 소개", audience="개발자", duration_minutes=20
            )

        assert artifact["type"] == "document"
        assert artifact["sub_command"] == "assist_presentation"
        assert "slides" in artifact
        assert isinstance(artifact["slides"], list)
        assert artifact["slides"][0]["slide_number"] == 1


# ---------------------------------------------------------------------------
# LLM failure handling
# ---------------------------------------------------------------------------


class TestLLMFailure:
    """LLM 호출 실패 시 에러 처리. Requirements: 4.6"""

    @pytest.mark.asyncio
    async def test_review_llm_failure_returns_error(self, tool: DocumentTool):
        """LLM 호출 실패 시 에러 아티팩트를 반환해야 합니다."""
        with patch("app.tool_agents.document_agent.tool.call_llm", new_callable=AsyncMock, side_effect=RuntimeError("API error")):
            _, artifact = await tool._arun(sub_command="review", document="test doc")

        assert artifact["type"] == "document"
        assert "error_message" in artifact
        assert "API error" in artifact["error_message"]
        assert artifact.get("sub_command") == "review"

    @pytest.mark.asyncio
    async def test_outline_report_llm_failure_returns_error(self, tool: DocumentTool):
        """outline_report에서 LLM 실패 시 에러 아티팩트를 반환해야 합니다."""
        with patch("app.tool_agents.document_agent.tool.call_llm", new_callable=AsyncMock, side_effect=RuntimeError("timeout")):
            _, artifact = await tool._arun(sub_command="outline_report", topic="test", purpose="test")

        assert "error_message" in artifact
        assert artifact.get("sub_command") == "outline_report"


# ---------------------------------------------------------------------------
# Factory and deprecated flags
# ---------------------------------------------------------------------------


class TestDeprecatedFlags:
    """기존 팩토리들의 deprecated 플래그 테스트."""

    def test_document_factory_not_deprecated(self):
        from app.tool_agents.document_agent.factory import DocumentFactory

        factory = DocumentFactory()
        assert factory.deprecated is False
        assert factory.agent_type == "document"
        assert factory.category == "Documentation"

    def test_document_review_factory_deprecated(self):
        from app.tool_agents.document_review_agent.factory import DocumentReviewFactory

        factory = DocumentReviewFactory()
        assert factory.deprecated is True

    def test_report_outline_factory_deprecated(self):
        from app.tool_agents.report_outline_agent.factory import ReportOutlineFactory

        factory = ReportOutlineFactory()
        assert factory.deprecated is True

    def test_presentation_helper_factory_deprecated(self):
        from app.tool_agents.presentation_helper_agent.factory import PresentationHelperFactory

        factory = PresentationHelperFactory()
        assert factory.deprecated is True


class TestDocumentFactory:
    """DocumentFactory 생성 테스트."""

    def test_factory_creates_tool(self):
        from app.tool_agents.document_agent.factory import DocumentFactory

        factory = DocumentFactory()
        tool = factory.create_tool({})
        assert tool.name == "document"
        assert isinstance(tool, DocumentTool)
