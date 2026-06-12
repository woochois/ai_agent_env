"""번들된 예제 Tool Agent 단위 테스트.

- echo_agent: 입력 반환
- calculator_agent: 안전 평가, 에러 처리
- rag_search_agent: ES mock 검색, ES 미가용 처리
"""

from __future__ import annotations

import pytest

from app.tool_agents.calculator_agent.factory import get_factory as calc_factory
from app.tool_agents.calculator_agent.tool import safe_eval
from app.tool_agents.echo_agent.factory import get_factory as echo_factory
from app.tool_agents.rag_search_agent.factory import RagSearchAgentFactory


# --- echo_agent ---


@pytest.mark.asyncio
async def test_echo_agent_returns_input():
    tool = echo_factory().create_tool({"type": "echo_agent", "name": "echo"})
    content, artifact = await tool._arun("안녕하세요")
    assert content == "안녕하세요"
    assert artifact == {"type": "echo_agent", "echoed": "안녕하세요"}


# --- calculator_agent ---


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("2 + 3", 5.0),
        ("2 + 3 * (4 - 1)", 11.0),
        ("10 / 4", 2.5),
        ("2 ** 10", 1024.0),
        ("-5 + 3", -2.0),
        ("17 % 5", 2.0),
    ],
)
def test_safe_eval_arithmetic(expr, expected):
    assert safe_eval(expr) == expected


def test_safe_eval_rejects_names():
    with pytest.raises(ValueError):
        safe_eval("__import__('os')")


def test_safe_eval_rejects_invalid_syntax():
    with pytest.raises(ValueError):
        safe_eval("2 +")


def test_safe_eval_division_by_zero():
    with pytest.raises(ZeroDivisionError):
        safe_eval("1 / 0")


@pytest.mark.asyncio
async def test_calculator_agent_success():
    tool = calc_factory().create_tool({"type": "calculator_agent", "name": "calculator"})
    content, artifact = await tool._arun("120 * 0.85")
    assert artifact["type"] == "calculator_agent"
    assert artifact["result"] == 102.0
    assert "error_message" not in artifact


@pytest.mark.asyncio
async def test_calculator_agent_error_becomes_artifact():
    """잘못된 수식은 예외 대신 error artifact로 변환된다."""
    tool = calc_factory().create_tool({"type": "calculator_agent", "name": "calculator"})
    content, artifact = await tool._arun("1 / 0")
    assert content == ""
    assert artifact["type"] == "calculator_agent"
    assert "error_message" in artifact
    assert artifact["result"] is None


# --- rag_search_agent ---


class _FakeESClient:
    def __init__(self, hits):
        self._hits = hits

    async def search(self, index, body, ignore_unavailable=True):
        return {"hits": {"hits": self._hits}}


@pytest.mark.asyncio
async def test_rag_agent_returns_documents():
    hits = [
        {"_score": 1.2, "_source": {"content": "문서 본문", "source": "doc1.pdf"}},
        {"_score": 0.9, "_source": {"content": "다른 문서", "title": "제목2"}},
    ]
    fake_es = _FakeESClient(hits)
    factory = RagSearchAgentFactory(es_provider=lambda: fake_es)
    tool = factory.create_tool({"type": "rag_search_agent", "name": "retrieve_document"})

    content, artifact = await tool._arun("검색어")
    assert artifact["type"] == "rag_search_agent"
    docs = artifact["documents"]
    assert len(docs) == 2
    assert docs[0]["reference"] == "doc1.pdf"
    assert docs[1]["reference"] == "제목2"


@pytest.mark.asyncio
async def test_rag_agent_handles_no_es():
    """ES provider가 None을 반환하면 graceful하게 빈 결과를 반환한다."""
    factory = RagSearchAgentFactory(es_provider=lambda: None)
    tool = factory.create_tool({"type": "rag_search_agent", "name": "retrieve_document"})
    content, artifact = await tool._arun("검색어")
    assert artifact["documents"] == []
    assert artifact["note"] == "elasticsearch_unavailable"


@pytest.mark.asyncio
async def test_rag_agent_search_error_becomes_artifact():
    class _FailingES:
        async def search(self, **kwargs):
            raise RuntimeError("ES down")

    factory = RagSearchAgentFactory(es_provider=lambda: _FailingES())
    tool = factory.create_tool({"type": "rag_search_agent", "name": "retrieve_document"})
    content, artifact = await tool._arun("검색어")
    assert "error_message" in artifact
    assert artifact["documents"] == []
