"""app/agents/sample_qa_agent.py 단위 테스트.

LLM 호출 mock을 사용한 Agent 응답 구조 테스트와
대화 기록 저장/조회 테스트를 수행합니다.

Requirements: 8.5
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# 테스트 환경 변수 설정 (import 전에 설정)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
os.environ.setdefault("ELASTICSEARCH_URL", "http://localhost:9200")

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import create_app  # noqa: E402


@pytest.fixture
def mock_db():
    """Mock Database 인스턴스를 생성합니다."""
    db = AsyncMock()
    db.connect = AsyncMock(return_value=True)
    db.health_check = AsyncMock(return_value=True)
    db.disconnect = AsyncMock()
    db.session_factory = AsyncMock()
    return db


@pytest.fixture
def mock_es():
    """Mock ElasticsearchClient 인스턴스를 생성합니다."""
    es = AsyncMock()
    es.connect = AsyncMock(return_value=es)
    es.is_healthy = AsyncMock(return_value=True)
    es.close = AsyncMock()
    es.client = AsyncMock()
    return es


@pytest.fixture
def test_app(mock_db, mock_es):
    """DB/ES 연결을 모킹한 테스트용 FastAPI 앱을 생성합니다."""
    with (
        patch("app.main.Database", return_value=mock_db),
        patch("app.main.ElasticsearchClient", return_value=mock_es),
    ):
        app = create_app()
        yield app


@pytest.fixture
async def client(test_app):
    """비동기 HTTP 테스트 클라이언트."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestAgentChatEndpoint:
    """POST /agent/chat 엔드포인트 테스트 - LLM mock 사용."""

    @pytest.mark.asyncio
    async def test_chat_returns_chat_response_structure(self, test_app, mock_db, mock_es):
        """POST /agent/chat 이 ChatResponse 구조를 반환합니다."""
        # mock: ES 검색 결과 없음
        mock_es.client.search = AsyncMock(
            return_value={"hits": {"hits": []}}
        )

        # mock: DB session (save conversation)
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.session_factory.return_value = mock_session

        # mock: LLM 응답
        mock_llm_response = MagicMock()
        mock_llm_response.content = "테스트 응답입니다."
        mock_llm_response.response_metadata = {
            "token_usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            }
        }

        with (
            patch("app.agents.sample_qa_agent._get_db", return_value=mock_db),
            patch("app.agents.sample_qa_agent._get_es", return_value=mock_es),
            patch(
                "app.agents.sample_qa_agent._invoke_llm",
                new_callable=AsyncMock,
                return_value=("테스트 응답입니다.", None),
            ),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    "/agent/chat",
                    json={"message": "안녕하세요"},
                )

        assert response.status_code == 200
        data = response.json()
        # ChatResponse 필수 필드 확인
        assert "response" in data
        assert "session_id" in data
        assert "sources" in data
        assert isinstance(data["response"], str)
        assert isinstance(data["session_id"], str)
        assert isinstance(data["sources"], list)

    @pytest.mark.asyncio
    async def test_chat_returns_llm_response_text(self, test_app, mock_db, mock_es):
        """LLM mock 응답 텍스트가 그대로 반환됩니다."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.session_factory.return_value = mock_session

        mock_es.client.search = AsyncMock(
            return_value={"hits": {"hits": []}}
        )

        expected_response = "이것은 LLM의 테스트 응답입니다."

        with (
            patch("app.agents.sample_qa_agent._get_db", return_value=mock_db),
            patch("app.agents.sample_qa_agent._get_es", return_value=mock_es),
            patch(
                "app.agents.sample_qa_agent._invoke_llm",
                new_callable=AsyncMock,
                return_value=(expected_response, None),
            ),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    "/agent/chat",
                    json={"message": "테스트 질문"},
                )

        data = response.json()
        assert data["response"] == expected_response

    @pytest.mark.asyncio
    async def test_chat_uses_provided_session_id(self, test_app, mock_db, mock_es):
        """제공된 session_id가 응답에 그대로 반환됩니다."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.session_factory.return_value = mock_session

        mock_es.client.search = AsyncMock(
            return_value={"hits": {"hits": []}}
        )

        with (
            patch("app.agents.sample_qa_agent._get_db", return_value=mock_db),
            patch("app.agents.sample_qa_agent._get_es", return_value=mock_es),
            patch(
                "app.agents.sample_qa_agent._invoke_llm",
                new_callable=AsyncMock,
                return_value=("응답", None),
            ),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    "/agent/chat",
                    json={"message": "질문", "session_id": "my-custom-session"},
                )

        data = response.json()
        assert data["session_id"] == "my-custom-session"

    @pytest.mark.asyncio
    async def test_chat_generates_session_id_if_not_provided(self, test_app, mock_db, mock_es):
        """session_id가 없으면 자동 생성된 UUID가 반환됩니다."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.session_factory.return_value = mock_session

        mock_es.client.search = AsyncMock(
            return_value={"hits": {"hits": []}}
        )

        with (
            patch("app.agents.sample_qa_agent._get_db", return_value=mock_db),
            patch("app.agents.sample_qa_agent._get_es", return_value=mock_es),
            patch(
                "app.agents.sample_qa_agent._invoke_llm",
                new_callable=AsyncMock,
                return_value=("응답", None),
            ),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    "/agent/chat",
                    json={"message": "질문"},
                )

        data = response.json()
        assert data["session_id"] is not None
        # UUID 형식 확인 (36자, 4개의 하이픈)
        assert len(data["session_id"]) == 36
        assert data["session_id"].count("-") == 4

    @pytest.mark.asyncio
    async def test_chat_includes_sources_from_es_search(self, test_app, mock_db, mock_es):
        """ES 검색 결과의 sources가 응답에 포함됩니다."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.session_factory.return_value = mock_session

        # ES가 문서 소스를 반환
        mock_es.client.search = AsyncMock(
            return_value={
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "content": "관련 문서 내용",
                                "metadata": {"source": "doc1.pdf"},
                            }
                        },
                        {
                            "_source": {
                                "content": "다른 문서",
                                "metadata": {"source": "doc2.pdf"},
                            }
                        },
                    ]
                }
            }
        )

        with (
            patch("app.agents.sample_qa_agent._get_db", return_value=mock_db),
            patch("app.agents.sample_qa_agent._get_es", return_value=mock_es),
            patch(
                "app.agents.sample_qa_agent._invoke_llm",
                new_callable=AsyncMock,
                return_value=("응답", None),
            ),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    "/agent/chat",
                    json={"message": "문서 검색 질문"},
                )

        data = response.json()
        assert "doc1.pdf" in data["sources"]
        assert "doc2.pdf" in data["sources"]

    @pytest.mark.asyncio
    async def test_chat_with_usage_metadata(self, test_app, mock_db, mock_es):
        """LLM이 usage 정보를 반환하면 응답에 포함됩니다."""
        from app.models.schemas import UsageMetadata

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.session_factory.return_value = mock_session

        mock_es.client.search = AsyncMock(
            return_value={"hits": {"hits": []}}
        )

        usage = UsageMetadata(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            duration_ms=1200.5,
            estimated_cost_usd=0.000045,
        )

        with (
            patch("app.agents.sample_qa_agent._get_db", return_value=mock_db),
            patch("app.agents.sample_qa_agent._get_es", return_value=mock_es),
            patch(
                "app.agents.sample_qa_agent._invoke_llm",
                new_callable=AsyncMock,
                return_value=("응답", usage),
            ),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    "/agent/chat",
                    json={"message": "사용량 테스트"},
                )

        data = response.json()
        assert data["usage"] is not None
        assert data["usage"]["prompt_tokens"] == 100
        assert data["usage"]["completion_tokens"] == 50
        assert data["usage"]["total_tokens"] == 150
        assert data["usage"]["duration_ms"] == 1200.5
        assert data["usage"]["estimated_cost_usd"] == 0.000045


class TestAgentHistoryEndpoint:
    """GET /agent/history 엔드포인트 테스트 - 대화 기록 조회."""

    @pytest.mark.asyncio
    async def test_history_without_session_id_returns_prompt(self, test_app, mock_db):
        """session_id 없이 호출하면 안내 메시지를 반환합니다."""
        with patch("app.agents.sample_qa_agent._get_db", return_value=mock_db):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/agent/history")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] is None
        assert data["messages"] == []
        assert "session_id" in data.get("message", "")

    @pytest.mark.asyncio
    async def test_history_with_session_id_returns_messages(self, test_app, mock_db):
        """session_id 지정 시 해당 세션의 대화 기록을 반환합니다."""
        # DB에서 대화 기록 조회 결과를 mock
        from datetime import datetime, timezone

        mock_rows = [
            ("user", "안녕하세요", datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)),
            ("assistant", "안녕하세요! 무엇을 도와드릴까요?", datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc)),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # session_factory()는 동기 호출이며, async context manager를 반환해야 함
        mock_db.session_factory = MagicMock(return_value=mock_session)

        with patch("app.agents.sample_qa_agent._get_db", return_value=mock_db):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/agent/history?session_id=test-session-123")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "안녕하세요"
        assert data["messages"][1]["role"] == "assistant"
        assert data["messages"][1]["content"] == "안녕하세요! 무엇을 도와드릴까요?"

    @pytest.mark.asyncio
    async def test_history_returns_empty_when_db_unavailable(self, test_app):
        """DB가 사용 불가능할 때 빈 메시지 목록을 반환합니다."""
        mock_db_none = MagicMock()
        mock_db_none.session_factory = None

        with patch("app.agents.sample_qa_agent._get_db", return_value=mock_db_none):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/agent/history?session_id=any-session")

        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == []

    @pytest.mark.asyncio
    async def test_history_returns_empty_when_db_query_fails(self, test_app, mock_db):
        """DB 쿼리가 실패할 때 빈 메시지 목록을 반환합니다."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB connection lost"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.session_factory.return_value = mock_session

        with patch("app.agents.sample_qa_agent._get_db", return_value=mock_db):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.get("/agent/history?session_id=failing-session")

        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == []


class TestConversationSaving:
    """대화 기록 저장 테스트 - POST /agent/chat 시 DB에 저장 확인."""

    @pytest.mark.asyncio
    async def test_chat_saves_user_and_assistant_messages(self, test_app, mock_db, mock_es):
        """채팅 시 사용자 메시지와 어시스턴트 응답이 모두 DB에 저장됩니다."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.session_factory.return_value = mock_session

        mock_es.client.search = AsyncMock(
            return_value={"hits": {"hits": []}}
        )

        with (
            patch("app.agents.sample_qa_agent._get_db", return_value=mock_db),
            patch("app.agents.sample_qa_agent._get_es", return_value=mock_es),
            patch(
                "app.agents.sample_qa_agent._invoke_llm",
                new_callable=AsyncMock,
                return_value=("AI 응답", None),
            ),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                await ac.post(
                    "/agent/chat",
                    json={"message": "저장 테스트"},
                )

        # session_factory가 두 번 호출됨 (user 저장 + assistant 저장)
        assert mock_db.session_factory.call_count >= 2

    @pytest.mark.asyncio
    async def test_chat_works_when_db_save_fails(self, test_app, mock_db, mock_es):
        """DB 저장이 실패해도 채팅 응답은 정상적으로 반환됩니다."""
        # DB session이 예외를 발생시키도록 설정
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB write error"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.session_factory.return_value = mock_session

        mock_es.client.search = AsyncMock(
            return_value={"hits": {"hits": []}}
        )

        with (
            patch("app.agents.sample_qa_agent._get_db", return_value=mock_db),
            patch("app.agents.sample_qa_agent._get_es", return_value=mock_es),
            patch(
                "app.agents.sample_qa_agent._invoke_llm",
                new_callable=AsyncMock,
                return_value=("정상 응답", None),
            ),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    "/agent/chat",
                    json={"message": "DB 실패 테스트"},
                )

        # DB 저장 실패에도 불구하고 정상 응답 반환
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "정상 응답"


class TestDocumentSearch:
    """ES 문서 검색 관련 테스트."""

    @pytest.mark.asyncio
    async def test_chat_returns_empty_sources_when_es_unavailable(self, test_app, mock_db):
        """ES가 사용 불가능할 때 sources가 빈 리스트입니다."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.session_factory.return_value = mock_session

        # ES client가 None인 경우
        mock_es_none = MagicMock()
        mock_es_none.client = None

        with (
            patch("app.agents.sample_qa_agent._get_db", return_value=mock_db),
            patch("app.agents.sample_qa_agent._get_es", return_value=mock_es_none),
            patch(
                "app.agents.sample_qa_agent._invoke_llm",
                new_callable=AsyncMock,
                return_value=("응답", None),
            ),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    "/agent/chat",
                    json={"message": "ES 없이 질문"},
                )

        data = response.json()
        assert data["sources"] == []

    @pytest.mark.asyncio
    async def test_chat_returns_empty_sources_when_es_search_fails(
        self, test_app, mock_db, mock_es
    ):
        """ES 검색이 실패할 때 sources가 빈 리스트입니다."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_db.session_factory.return_value = mock_session

        mock_es.client.search = AsyncMock(side_effect=Exception("ES error"))

        with (
            patch("app.agents.sample_qa_agent._get_db", return_value=mock_db),
            patch("app.agents.sample_qa_agent._get_es", return_value=mock_es),
            patch(
                "app.agents.sample_qa_agent._invoke_llm",
                new_callable=AsyncMock,
                return_value=("응답", None),
            ),
        ):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    "/agent/chat",
                    json={"message": "ES 에러 질문"},
                )

        data = response.json()
        assert data["sources"] == []
