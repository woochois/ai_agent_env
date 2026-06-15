"""Communication Agent 단위 테스트.

sub_command 라우팅, 입력 검증, 에러 처리, 재시도 로직, JSON 파싱 폴백을 검증합니다.

Property 1: Expert Agent Sub_Command 라우팅 및 입력 검증
Property 7: LLM 호출 실패 시 에러 아티팩트 및 재시도
Property 8: LLM JSON 파싱 실패 시 원본 텍스트 보존

Validates: Requirements 3.2, 3.3, 3.4, 3.6, 3.7, 3.8, 3.9, 3.10
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.tool_agents.communication_agent.tool import AGENT_TYPE, CommunicationTool


@pytest.fixture
def tool():
    """CommunicationTool 인스턴스를 생성합니다."""
    return CommunicationTool()


# ---------------------------------------------------------------------------
# Sub_command validation - invalid sub_commands (Requirement 3.9)
# ---------------------------------------------------------------------------


class TestInvalidSubCommand:
    """유효하지 않은 sub_command 테스트."""

    @pytest.mark.asyncio
    async def test_unknown_sub_command_returns_error_artifact(self, tool: CommunicationTool):
        """알 수 없는 sub_command는 에러 아티팩트를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="unknown_command")
        assert artifact["type"] == AGENT_TYPE
        assert "error_message" in artifact
        assert "unknown_command" in artifact["error_message"]

    @pytest.mark.asyncio
    async def test_unknown_sub_command_includes_valid_list(self, tool: CommunicationTool):
        """에러 아티팩트에 유효한 sub_command 목록이 포함되어야 합니다."""
        _, artifact = await tool._arun(sub_command="bad")
        assert "valid_sub_commands" in artifact
        valid = artifact["valid_sub_commands"]
        assert "draft_email" in valid
        assert "translate" in valid
        assert "summarize_meeting" in valid

    @pytest.mark.asyncio
    async def test_unknown_sub_command_includes_requested_value(self, tool: CommunicationTool):
        """에러 아티팩트에 요청된 sub_command 값이 포함되어야 합니다."""
        _, artifact = await tool._arun(sub_command="foobar")
        assert artifact.get("requested_sub_command") == "foobar"

    @pytest.mark.asyncio
    async def test_empty_sub_command_returns_error(self, tool: CommunicationTool):
        """빈 문자열 sub_command는 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(sub_command="")
        assert "error_message" in artifact
        assert "valid_sub_commands" in artifact


# ---------------------------------------------------------------------------
# Required fields validation (Requirement 3.8)
# ---------------------------------------------------------------------------


class TestRequiredFieldsValidation:
    """필수 필드 누락 시 에러 아티팩트 테스트."""

    @pytest.mark.asyncio
    async def test_draft_email_missing_purpose(self, tool: CommunicationTool):
        """draft_email에서 purpose가 비어있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(
            sub_command="draft_email",
            purpose="",
            recipient="CEO",
            key_points="내용",
        )
        assert "error_message" in artifact
        assert "purpose" in artifact["missing_fields"]

    @pytest.mark.asyncio
    async def test_draft_email_missing_multiple_fields(self, tool: CommunicationTool):
        """draft_email에서 여러 필수 필드가 비어있으면 모두 나열해야 합니다."""
        _, artifact = await tool._arun(
            sub_command="draft_email",
            purpose="",
            recipient="",
            key_points="",
        )
        assert "error_message" in artifact
        assert "purpose" in artifact["missing_fields"]
        assert "recipient" in artifact["missing_fields"]
        assert "key_points" in artifact["missing_fields"]

    @pytest.mark.asyncio
    async def test_translate_missing_text(self, tool: CommunicationTool):
        """translate에서 text가 비어있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(
            sub_command="translate",
            text="",
            target_lang="en",
        )
        assert "error_message" in artifact
        assert "text" in artifact["missing_fields"]

    @pytest.mark.asyncio
    async def test_translate_missing_target_lang(self, tool: CommunicationTool):
        """translate에서 target_lang이 비어있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(
            sub_command="translate",
            text="안녕하세요",
            target_lang="",
        )
        assert "error_message" in artifact
        assert "target_lang" in artifact["missing_fields"]

    @pytest.mark.asyncio
    async def test_summarize_meeting_missing_content(self, tool: CommunicationTool):
        """summarize_meeting에서 content가 비어있으면 에러를 반환해야 합니다."""
        _, artifact = await tool._arun(
            sub_command="summarize_meeting",
            content="",
        )
        assert "error_message" in artifact
        assert "content" in artifact["missing_fields"]

    @pytest.mark.asyncio
    async def test_whitespace_only_treated_as_empty(self, tool: CommunicationTool):
        """공백만 있는 필드는 비어있는 것으로 취급해야 합니다."""
        _, artifact = await tool._arun(
            sub_command="translate",
            text="   ",
            target_lang="en",
        )
        assert "error_message" in artifact
        assert "text" in artifact["missing_fields"]


# ---------------------------------------------------------------------------
# Successful LLM calls with mocked call_llm (Requirements 3.2, 3.3, 3.4)
# ---------------------------------------------------------------------------


class TestDraftEmail:
    """draft_email sub_command 성공 케이스."""

    @pytest.mark.asyncio
    @patch("app.tool_agents.communication_agent.tool.call_llm")
    async def test_draft_email_valid_json(self, mock_llm, tool: CommunicationTool):
        """LLM이 올바른 JSON을 반환하면 subject/body가 artifact에 포함됩니다."""
        mock_llm.return_value = '{"subject": "프로젝트 업데이트", "body": "안녕하세요, 김 대리님."}'

        content, artifact = await tool._arun(
            sub_command="draft_email",
            purpose="프로젝트 보고",
            recipient="김 대리",
            key_points="진행 상황 공유",
        )

        assert artifact["type"] == AGENT_TYPE
        assert artifact["sub_command"] == "draft_email"
        assert artifact["subject"] == "프로젝트 업데이트"
        assert artifact["body"] == "안녕하세요, 김 대리님."
        assert "프로젝트 업데이트" in content


class TestTranslate:
    """translate sub_command 성공 케이스."""

    @pytest.mark.asyncio
    @patch("app.tool_agents.communication_agent.tool.call_llm")
    async def test_translate_valid_json(self, mock_llm, tool: CommunicationTool):
        """LLM이 올바른 JSON을 반환하면 번역 결과가 artifact에 포함됩니다."""
        mock_llm.return_value = (
            '{"source_text": "안녕하세요", "translated_text": "Hello", '
            '"source_lang": "ko", "target_lang": "en"}'
        )

        content, artifact = await tool._arun(
            sub_command="translate",
            text="안녕하세요",
            target_lang="en",
        )

        assert artifact["type"] == AGENT_TYPE
        assert artifact["sub_command"] == "translate"
        assert artifact["source_text"] == "안녕하세요"
        assert artifact["translated_text"] == "Hello"
        assert artifact["source_lang"] == "ko"
        assert artifact["target_lang"] == "en"


class TestSummarizeMeeting:
    """summarize_meeting sub_command 성공 케이스."""

    @pytest.mark.asyncio
    @patch("app.tool_agents.communication_agent.tool.call_llm")
    async def test_summarize_meeting_valid_json(self, mock_llm, tool: CommunicationTool):
        """LLM이 올바른 JSON을 반환하면 구조화된 요약이 artifact에 포함됩니다."""
        mock_llm.return_value = (
            '{"title": "주간회의", "attendees": ["김팀장", "이사원"], '
            '"agenda": ["진행 현황"], "decisions": ["계속 진행"], '
            '"action_items": [{"assignee": "이사원", "task": "보고서 작성", "deadline": "금요일"}]}'
        )

        content, artifact = await tool._arun(
            sub_command="summarize_meeting",
            content="김팀장, 이사원 참석. 주간 진행 현황 논의.",
            meeting_title="주간회의",
        )

        assert artifact["type"] == AGENT_TYPE
        assert artifact["sub_command"] == "summarize_meeting"
        assert artifact["title"] == "주간회의"
        assert artifact["attendees"] == ["김팀장", "이사원"]
        assert artifact["agenda"] == ["진행 현황"]
        assert artifact["decisions"] == ["계속 진행"]
        assert len(artifact["action_items"]) == 1
        assert artifact["action_items"][0]["assignee"] == "이사원"


# ---------------------------------------------------------------------------
# Retry logic (Requirement 3.6) - Property 7
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """LLM 호출 재시도 로직 테스트."""

    @pytest.mark.asyncio
    @patch("app.tool_agents.communication_agent.tool.call_llm")
    async def test_retry_on_first_failure_then_success(self, mock_llm, tool: CommunicationTool):
        """첫 번째 호출이 실패하고 재시도가 성공하면 정상 결과를 반환해야 합니다."""
        mock_llm.side_effect = [
            RuntimeError("LLM 일시 오류"),
            '{"subject": "테스트", "body": "본문"}',
        ]

        content, artifact = await tool._arun(
            sub_command="draft_email",
            purpose="테스트",
            recipient="수신자",
            key_points="내용",
        )

        assert artifact["type"] == AGENT_TYPE
        assert artifact["subject"] == "테스트"
        assert mock_llm.call_count == 2

    @pytest.mark.asyncio
    @patch("app.tool_agents.communication_agent.tool.call_llm")
    async def test_retry_both_failures_returns_error(self, mock_llm, tool: CommunicationTool):
        """두 번 모두 실패하면 에러 아티팩트를 반환해야 합니다."""
        mock_llm.side_effect = [
            RuntimeError("1차 실패"),
            RuntimeError("2차 실패"),
        ]

        content, artifact = await tool._arun(
            sub_command="draft_email",
            purpose="테스트",
            recipient="수신자",
            key_points="내용",
        )

        # auto_error_artifact가 에러를 잡아서 error artifact를 반환
        assert artifact["type"] == AGENT_TYPE
        assert "error_message" in artifact
        assert mock_llm.call_count == 2

    @pytest.mark.asyncio
    @patch("app.tool_agents.communication_agent.tool.call_llm")
    async def test_retry_exactly_once(self, mock_llm, tool: CommunicationTool):
        """실패 시 정확히 1회만 재시도해야 합니다 (총 2회 호출)."""
        mock_llm.side_effect = [
            RuntimeError("실패 1"),
            RuntimeError("실패 2"),
        ]

        await tool._arun(
            sub_command="translate",
            text="hello",
            target_lang="ko",
        )

        assert mock_llm.call_count == 2


# ---------------------------------------------------------------------------
# JSON parse fallback (Requirement 3.7) - Property 8
# ---------------------------------------------------------------------------


class TestJsonParseFallback:
    """JSON 파싱 실패 시 raw text를 content로 사용하는 테스트."""

    @pytest.mark.asyncio
    @patch("app.tool_agents.communication_agent.tool.call_llm")
    async def test_draft_email_non_json_uses_raw_text(self, mock_llm, tool: CommunicationTool):
        """LLM 응답이 JSON이 아니면 raw text를 content 필드에 저장해야 합니다."""
        raw_text = "이것은 JSON이 아닌 일반 텍스트 응답입니다."
        mock_llm.return_value = raw_text

        content, artifact = await tool._arun(
            sub_command="draft_email",
            purpose="테스트",
            recipient="수신자",
            key_points="내용",
        )

        assert artifact["type"] == AGENT_TYPE
        assert artifact["content"] == raw_text
        assert content == raw_text

    @pytest.mark.asyncio
    @patch("app.tool_agents.communication_agent.tool.call_llm")
    async def test_translate_non_json_uses_raw_text(self, mock_llm, tool: CommunicationTool):
        """translate에서 JSON 파싱 실패 시 raw text를 content 필드에 저장해야 합니다."""
        raw_text = "번역 결과: Hello World"
        mock_llm.return_value = raw_text

        content, artifact = await tool._arun(
            sub_command="translate",
            text="안녕하세요",
            target_lang="en",
        )

        assert artifact["type"] == AGENT_TYPE
        assert artifact["content"] == raw_text
        assert content == raw_text

    @pytest.mark.asyncio
    @patch("app.tool_agents.communication_agent.tool.call_llm")
    async def test_summarize_meeting_non_json_uses_raw_text(self, mock_llm, tool: CommunicationTool):
        """summarize_meeting에서 JSON 파싱 실패 시 raw text를 content 필드에 저장해야 합니다."""
        raw_text = "회의 요약: 프로젝트 관련 논의 진행"
        mock_llm.return_value = raw_text

        content, artifact = await tool._arun(
            sub_command="summarize_meeting",
            content="회의 내용 텍스트",
        )

        assert artifact["type"] == AGENT_TYPE
        assert artifact["content"] == raw_text
        assert content == raw_text

    @pytest.mark.asyncio
    @patch("app.tool_agents.communication_agent.tool.call_llm")
    async def test_partial_json_missing_key_uses_raw_text(self, mock_llm, tool: CommunicationTool):
        """JSON은 유효하지만 필수 키가 없으면 raw text를 사용해야 합니다."""
        # draft_email은 subject와 body 모두 필요
        mock_llm.return_value = '{"subject": "제목만 있음"}'

        content, artifact = await tool._arun(
            sub_command="draft_email",
            purpose="테스트",
            recipient="수신자",
            key_points="내용",
        )

        assert artifact["type"] == AGENT_TYPE
        # subject만 있고 body가 없으므로 fallback
        assert artifact["content"] == '{"subject": "제목만 있음"}'


# ---------------------------------------------------------------------------
# Factory deprecated flags (Requirement 3.10)
# ---------------------------------------------------------------------------


class TestDeprecatedFlags:
    """기존 팩토리들의 deprecated 플래그 테스트."""

    def test_communication_factory_not_deprecated(self):
        from app.tool_agents.communication_agent.factory import CommunicationFactory

        factory = CommunicationFactory()
        assert factory.deprecated is False

    def test_email_draft_factory_deprecated(self):
        from app.tool_agents.email_draft_agent.factory import EmailDraftFactory

        factory = EmailDraftFactory()
        assert factory.deprecated is True

    def test_translation_factory_deprecated(self):
        from app.tool_agents.translation_agent.factory import TranslationFactory

        factory = TranslationFactory()
        assert factory.deprecated is True

    def test_meeting_summary_factory_deprecated(self):
        from app.tool_agents.meeting_summary_agent.factory import MeetingSummaryFactory

        factory = MeetingSummaryFactory()
        assert factory.deprecated is True


# ---------------------------------------------------------------------------
# Factory creation
# ---------------------------------------------------------------------------


class TestCommunicationFactory:
    """CommunicationFactory 생성 테스트."""

    def test_factory_creates_tool(self):
        from app.tool_agents.communication_agent.factory import CommunicationFactory

        factory = CommunicationFactory()
        tool = factory.create_tool({})
        assert tool.name == "communication"
        assert isinstance(tool, CommunicationTool)

    def test_factory_agent_type(self):
        from app.tool_agents.communication_agent.factory import CommunicationFactory

        factory = CommunicationFactory()
        assert factory.agent_type == "communication"
        assert factory.category == "Communication"
