"""FastAPI 앱 진입점.

FastAPI 인스턴스를 생성하고, 설정 로드, 로깅 초기화, 전역 예외 핸들러,
라우터 등록, 서비스 연결 초기화(lifespan)를 수행합니다.

Requirements: 2.3, 2.5, 8.3
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.logging_config import setup_logging
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
)
from app.services.database import Database
from app.services.elasticsearch import ElasticsearchClient

logger = logging.getLogger(__name__)

# 서비스 시작 시간 (uptime 계산용)
_start_time: float = 0.0

# 전역 서비스 인스턴스
db: Database | None = None
es: ElasticsearchClient | None = None


def get_start_time() -> float:
    """서비스 시작 시간을 반환합니다."""
    return _start_time


def get_db() -> Database | None:
    """전역 Database 인스턴스를 반환합니다."""
    return db


def get_es() -> ElasticsearchClient | None:
    """전역 ElasticsearchClient 인스턴스를 반환합니다."""
    return es


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """애플리케이션 lifespan 이벤트 핸들러.

    서비스 시작 시 DB/ES 연결을 초기화하고, 종료 시 연결을 정리합니다.
    연결 실패 시에도 서비스는 시작되며 헬스체크에서 unhealthy로 표시됩니다.
    """
    global _start_time, db, es

    _start_time = time.time()

    # Database 연결 초기화
    db = Database()
    db_connected = await db.connect()
    if not db_connected:
        logger.error(
            "Database connection failed during startup",
            extra={"service": "database"},
        )

    # Elasticsearch 연결 초기화
    es = ElasticsearchClient()
    es_client = await es.connect()
    if es_client is None:
        logger.error(
            "Elasticsearch connection failed during startup",
            extra={"service": "elasticsearch"},
        )

    logger.info("Application startup complete")

    yield

    # Shutdown: 연결 정리
    if db is not None:
        await db.disconnect()
    if es is not None:
        await es.close()

    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """FastAPI 애플리케이션을 생성하고 설정합니다.

    Returns:
        설정된 FastAPI 앱 인스턴스.
    """
    # 설정 로드 및 로깅 초기화
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL)

    app = FastAPI(
        title="AI Agent Server",
        description="LangChain 기반 AI Agent 개발 서버",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 전역 예외 핸들러 등록
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """처리되지 않은 예외를 HTTP 500으로 변환합니다.

        예외 정보를 로깅하고, 서비스는 계속 실행됩니다.
        """
        request_id = str(uuid.uuid4())

        logger.error(
            "Unhandled exception: %s",
            str(exc),
            extra={
                "request_id": request_id,
                "exception_type": type(exc).__name__,
                "path": str(request.url.path),
            },
            exc_info=True,
        )

        # DEBUG 모드에서만 상세 정보를 노출
        detail = str(exc) if settings.DEBUG_MODE else None

        error_response = ErrorResponse(
            error=type(exc).__name__,
            message="내부 서버 오류가 발생했습니다.",
            detail=detail,
            request_id=request_id,
        )

        return JSONResponse(
            status_code=500,
            content=error_response.model_dump(),
        )

    # 라우터 및 플레이스홀더 엔드포인트 등록
    _register_routes(app)

    # Static 파일 서빙 (UI)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", response_class=HTMLResponse, tags=["ui"])
        async def serve_ui() -> HTMLResponse:
            """웹 UI를 제공합니다."""
            html_path = static_dir / "index.html"
            return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    return app


def _register_routes(app: FastAPI) -> None:
    """라우터와 엔드포인트를 등록합니다.

    전용 모듈(app.health, app.agents.sample_qa_agent)이 존재하면 해당 라우터를
    사용하고, 없으면 플레이스홀더 엔드포인트를 직접 등록합니다.
    /docs는 FastAPI가 자동 생성합니다 (Swagger UI).
    """
    # 헬스체크 라우터 등록
    _health_registered = False
    try:
        from app.health import router as health_router

        app.include_router(health_router)
        _health_registered = True
    except ImportError:
        logger.info("Health router module not found, using placeholder endpoint")

    if not _health_registered:
        @app.get("/health", response_model=HealthResponse, tags=["health"])
        async def health_check() -> HealthResponse:
            """헬스체크 플레이스홀더 엔드포인트.

            실제 구현은 task 7.2에서 app/health.py로 이전됩니다.
            """
            uptime = time.time() - _start_time

            db_status = "disconnected"
            if db is not None:
                try:
                    db_healthy = await db.health_check()
                    db_status = "connected" if db_healthy else "disconnected"
                except Exception:
                    db_status = "disconnected"

            es_status = "disconnected"
            if es is not None:
                try:
                    es_healthy = await es.is_healthy()
                    es_status = "connected" if es_healthy else "disconnected"
                except Exception:
                    es_status = "disconnected"

            if db_status == "connected" and es_status == "connected":
                status = "healthy"
            elif db_status == "disconnected" and es_status == "disconnected":
                status = "unhealthy"
            else:
                status = "degraded"

            return HealthResponse(
                status=status,
                database=db_status,
                elasticsearch=es_status,
                uptime_seconds=round(uptime, 2),
            )

    # Agent 라우터 등록
    _agent_registered = False
    try:
        from app.agents.sample_qa_agent import router as agent_router

        app.include_router(agent_router, prefix="/agent")
        _agent_registered = True
    except ImportError:
        logger.info("Agent router module not found, using placeholder endpoints")

    # Supervisor (프레임워크) 라우터 등록
    try:
        from app.agents.supervisor_router import router as supervisor_router

        app.include_router(supervisor_router, prefix="/agent")
        logger.info("Supervisor router registered")
    except ImportError as exc:
        logger.info("Supervisor router not available: %s", exc)

    # AI Ops 라우터 등록
    try:
        from app.agents.ops_router import router as ops_router

        app.include_router(ops_router)
        logger.info("Ops router registered")
    except ImportError as exc:
        logger.info("Ops router not available: %s", exc)

    if not _agent_registered:
        @app.post("/agent/chat", response_model=ChatResponse, tags=["agent"])
        async def agent_chat(request: ChatRequest) -> ChatResponse:
            """Agent 대화 플레이스홀더 엔드포인트.

            실제 구현은 task 9.1에서 app/agents/sample_qa_agent.py로 이전됩니다.
            """
            session_id = request.session_id or str(uuid.uuid4())
            return ChatResponse(
                response="Agent가 아직 구현되지 않았습니다. 샘플 응답입니다.",
                session_id=session_id,
                sources=[],
                usage=None,
            )

        @app.get("/agent/history", tags=["agent"])
        async def agent_history(session_id: str | None = None) -> dict:
            """대화 기록 조회 플레이스홀더 엔드포인트.

            실제 구현은 task 9.1에서 app/agents/sample_qa_agent.py로 이전됩니다.
            """
            return {
                "session_id": session_id,
                "messages": [],
                "message": "대화 기록 조회가 아직 구현되지 않았습니다.",
            }


# 앱 인스턴스 생성
app = create_app()
