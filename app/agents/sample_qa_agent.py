"""샘플 Q&A Agent 모듈.

LangChain 기반 Q&A Agent를 구현합니다. POST /chat 엔드포인트로 사용자 질문을
받아 Elasticsearch에서 관련 문서를 검색하고, LLM을 통해 응답을 생성하며,
대화 기록을 PostgreSQL에 저장합니다. GET /history 엔드포인트로 대화 기록을
조회할 수 있습니다.

Requirements: 8.5
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from sqlalchemy import text

from app.models.schemas import ChatRequest, ChatResponse, UsageMetadata
from app.services.llm import CostTrackingCallback, calculate_cost

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent"])


def _get_db():
    """전역 Database 인스턴스를 가져옵니다."""
    from app.main import get_db
    return get_db()


def _get_es():
    """전역 ElasticsearchClient 인스턴스를 가져옵니다."""
    from app.main import get_es
    return get_es()


async def _search_documents(query: str, top_k: int = 3) -> list[str]:
    """Elasticsearch에서 관련 문서를 검색합니다.

    ES가 연결되지 않았거나 검색 실패 시 빈 리스트를 반환합니다.

    Args:
        query: 검색 쿼리 문자열.
        top_k: 반환할 최대 문서 수.

    Returns:
        검색된 문서 소스 목록.
    """
    es = _get_es()
    if es is None or es.client is None:
        logger.warning(
            "Elasticsearch not available, skipping document search",
            extra={"service": "elasticsearch"},
        )
        return []

    try:
        # multi_match 쿼리로 content 필드 검색
        search_body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["content", "metadata.source"],
                }
            },
            "size": top_k,
            "_source": ["content", "metadata.source"],
        }

        # documents 인덱스에서 검색 (인덱스가 없으면 빈 결과)
        response = await es.client.search(
            index="documents",
            body=search_body,
            ignore_unavailable=True,
        )

        sources = []
        hits = response.get("hits", {}).get("hits", [])
        for hit in hits:
            source = hit.get("_source", {})
            # metadata.source 필드가 있으면 출처로 사용
            metadata = source.get("metadata", {})
            doc_source = metadata.get("source", "")
            if doc_source:
                sources.append(doc_source)
            elif source.get("content"):
                # source가 없으면 content 앞부분을 출처로 사용
                content_preview = source["content"][:100]
                sources.append(content_preview)

        return sources

    except Exception as exc:
        logger.warning(
            "Document search failed: %s",
            exc,
            extra={"service": "elasticsearch", "error": str(exc)},
        )
        return []


async def _save_conversation(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[dict] = None,
) -> None:
    """대화 기록을 PostgreSQL에 저장합니다.

    DB가 연결되지 않았거나 저장 실패 시 경고 로그만 남기고 진행합니다.

    Args:
        session_id: 대화 세션 식별자.
        role: 발화자 역할 ('user', 'assistant', 'system').
        content: 메시지 내용.
        metadata: 추가 메타데이터 (JSON).
    """
    db = _get_db()
    if db is None or db.session_factory is None:
        logger.warning(
            "Database not available, skipping conversation save",
            extra={"service": "database"},
        )
        return

    try:
        async with db.session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO conversations (id, session_id, role, content, metadata, created_at)
                    VALUES (:id, :session_id, :role, :content, :metadata, :created_at)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "role": role,
                    "content": content,
                    "metadata": str(metadata or {}),
                    "created_at": datetime.now(timezone.utc),
                },
            )
            await session.commit()
    except Exception as exc:
        logger.warning(
            "Failed to save conversation: %s",
            exc,
            extra={"service": "database", "error": str(exc)},
        )


async def _get_conversation_history(session_id: str) -> list[dict]:
    """세션의 대화 기록을 조회합니다.

    Args:
        session_id: 대화 세션 식별자.

    Returns:
        대화 기록 목록 (role, content, created_at 포함).
    """
    db = _get_db()
    if db is None or db.session_factory is None:
        return []

    try:
        async with db.session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT role, content, created_at
                    FROM conversations
                    WHERE session_id = :session_id
                    ORDER BY created_at ASC
                    """
                ),
                {"session_id": session_id},
            )
            rows = result.fetchall()
            return [
                {
                    "role": row[0],
                    "content": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                }
                for row in rows
            ]
    except Exception as exc:
        logger.warning(
            "Failed to retrieve conversation history: %s",
            exc,
            extra={"service": "database", "error": str(exc)},
        )
        return []


async def _invoke_llm(
    message: str,
    context: list[str],
    session_id: str,
) -> tuple[str, Optional[UsageMetadata]]:
    """LangChain ChatOpenAI를 사용하여 LLM 응답을 생성합니다.

    CostTrackingCallback을 적용하여 비용을 추적합니다.

    Args:
        message: 사용자 메시지.
        context: 검색된 문서 컨텍스트 목록.
        session_id: 대화 세션 ID.

    Returns:
        (응답 텍스트, 사용량 메타데이터) 튜플.
    """
    import time

    from app.config import get_settings

    settings = get_settings()

    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        try:
            from langchain_community.chat_models import ChatOpenAI
        except ImportError:
            from langchain.chat_models import ChatOpenAI

    from langchain_core.messages import HumanMessage, SystemMessage

    # CostTrackingCallback 인스턴스 생성
    cost_callback = CostTrackingCallback()

    # ChatOpenAI 인스턴스 생성
    try:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            callbacks=[cost_callback],
        )
    except Exception as exc:
        logger.error(
            "Failed to initialize ChatOpenAI: %s",
            exc,
            extra={"error": str(exc)},
        )
        return (
            "LLM 초기화에 실패했습니다. API 키를 확인해주세요.",
            None,
        )

    # 시스템 프롬프트 구성
    system_prompt = (
        "당신은 도움이 되는 AI 어시스턴트입니다. "
        "사용자의 질문에 정확하고 친절하게 답변해주세요."
    )

    if context:
        context_text = "\n\n".join(context)
        system_prompt += (
            f"\n\n다음은 참고할 수 있는 관련 문서입니다:\n{context_text}"
        )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=message),
    ]

    # LLM 호출
    start_time = time.perf_counter()
    try:
        response = await llm.ainvoke(messages)
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # 응답에서 사용량 정보 추출
        usage_metadata = None
        response_meta = getattr(response, "response_metadata", {}) or {}
        token_usage = response_meta.get("token_usage") or {}

        if token_usage:
            prompt_tokens = int(token_usage.get("prompt_tokens", 0) or 0)
            completion_tokens = int(
                token_usage.get("completion_tokens", 0) or 0
            )
            total_tokens = int(token_usage.get("total_tokens", 0) or 0)
            if total_tokens == 0:
                total_tokens = prompt_tokens + completion_tokens

            estimated_cost = calculate_cost(
                "gpt-4o-mini", prompt_tokens, completion_tokens
            )

            usage_metadata = UsageMetadata(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                duration_ms=round(duration_ms, 3),
                estimated_cost_usd=estimated_cost,
            )

        return (response.content, usage_metadata)

    except Exception as exc:
        logger.error(
            "LLM invocation failed: %s",
            exc,
            extra={"error": str(exc), "session_id": session_id},
        )
        return (
            "죄송합니다. 응답 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            None,
        )


@router.post("/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest) -> ChatResponse:
    """Agent 대화 엔드포인트.

    사용자 메시지를 받아 관련 문서를 검색하고, LLM으로 응답을 생성한 뒤,
    대화 기록을 저장합니다.

    Args:
        request: ChatRequest (message, session_id).

    Returns:
        ChatResponse: 생성된 응답, 세션 ID, 참조 소스, 사용량 정보.
    """
    session_id = request.session_id or str(uuid.uuid4())

    # 1. Elasticsearch에서 관련 문서 검색
    sources = await _search_documents(request.message)

    # 2. 사용자 메시지를 DB에 저장
    await _save_conversation(session_id, "user", request.message)

    # 3. LLM 호출
    response_text, usage = await _invoke_llm(
        message=request.message,
        context=sources,
        session_id=session_id,
    )

    # 4. 어시스턴트 응답을 DB에 저장
    await _save_conversation(
        session_id,
        "assistant",
        response_text,
        metadata={"sources": sources} if sources else None,
    )

    return ChatResponse(
        response=response_text,
        session_id=session_id,
        sources=sources,
        usage=usage,
    )


@router.get("/history")
async def agent_history(session_id: Optional[str] = None) -> dict:
    """대화 기록 조회 엔드포인트.

    세션 ID로 대화 기록을 조회합니다. 세션 ID가 없으면 빈 목록을 반환합니다.

    Args:
        session_id: 조회할 대화 세션 식별자 (optional).

    Returns:
        대화 기록 딕셔너리 (session_id, messages).
    """
    if not session_id:
        return {
            "session_id": None,
            "messages": [],
            "message": "session_id를 지정해주세요.",
        }

    messages = await _get_conversation_history(session_id)

    return {
        "session_id": session_id,
        "messages": messages,
    }
