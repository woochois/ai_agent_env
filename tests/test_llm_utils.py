"""parse_json_response() 유닛 테스트.

LLM 응답에서 JSON을 추출하는 헬퍼 함수의 동작을 검증합니다.
"""

from __future__ import annotations

import pytest

from app.tool_agents._llm_utils import parse_json_response


class TestParseJsonResponse:
    """parse_json_response 함수 테스트."""

    def test_extracts_json_from_json_code_block(self):
        """```json ... ``` 코드 블록에서 JSON을 추출한다."""
        response = '여기에 결과입니다:\n```json\n{"key": "value", "num": 42}\n```\n끝.'
        result = parse_json_response(response)
        assert result == {"key": "value", "num": 42}

    def test_extracts_json_from_plain_code_block(self):
        """``` ... ``` (json 태그 없는) 코드 블록에서도 JSON을 추출한다."""
        response = '결과:\n```\n{"name": "test"}\n```'
        result = parse_json_response(response)
        assert result == {"name": "test"}

    def test_parses_raw_json_string(self):
        """코드 블록 없이 순수 JSON 문자열을 파싱한다."""
        response = '{"type": "email_draft_agent", "subject": "회의 안내"}'
        result = parse_json_response(response)
        assert result == {"type": "email_draft_agent", "subject": "회의 안내"}

    def test_parses_json_with_leading_trailing_whitespace(self):
        """앞뒤 공백이 있는 JSON을 정상 파싱한다."""
        response = '  \n {"hello": "world"} \n  '
        result = parse_json_response(response)
        assert result == {"hello": "world"}

    def test_returns_none_for_invalid_text(self):
        """JSON이 아닌 일반 텍스트에 대해 None을 반환한다."""
        response = "이것은 그냥 텍스트입니다."
        result = parse_json_response(response)
        assert result is None

    def test_returns_none_for_invalid_json_in_code_block(self):
        """코드 블록 내부에 유효하지 않은 JSON이 있으면 None을 반환한다."""
        response = '```json\n{invalid json content\n```'
        result = parse_json_response(response)
        assert result is None

    def test_extracts_nested_json_from_code_block(self):
        """중첩 구조의 JSON도 코드 블록에서 추출한다."""
        nested = '{"slides": [{"title": "소개", "points": ["A", "B"]}]}'
        response = f"발표 구성:\n```json\n{nested}\n```"
        result = parse_json_response(response)
        assert result == {"slides": [{"title": "소개", "points": ["A", "B"]}]}

    def test_empty_string_returns_none(self):
        """빈 문자열에 대해 None을 반환한다."""
        assert parse_json_response("") is None

    def test_code_block_takes_priority_over_raw_json(self):
        """코드 블록과 raw JSON이 둘 다 있으면 코드 블록을 우선 추출한다."""
        response = '{"outside": true}\n```json\n{"inside": true}\n```'
        result = parse_json_response(response)
        assert result == {"inside": True}
