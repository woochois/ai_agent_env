"""헬스체크 엔드포인트 모듈.

GET /health 엔드포인트를 제공하며, Database 및 Elasticsearch의 연결 상태를
확인하여 전체 서비스 상태를 반환합니다.

상태 판단 기준:
- "healthy": DB와 ES 모두 정상 연결
- "degraded": 하나만 연결 실패
- "unhealthy": 모두 연결 실패

5초 이내 응답을 보장하기 위해 각 서비스 체크에 타임아웃을 적용합니다.

Requirements: 2.4, 2.7
"""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter

from app.models.schemas import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

# 각 서비스 헬스체크의 개별 타임아웃 (초)
_HEALTH_CHECK_TIMEOUT = 4.0


async def _check_db_health() -> str:
    """Database 연결 상태를 확인합니다.

    Returns:
        "connected" 또는 "disconnected".
    """
    from app.main import get_db

    db = get_db()
    if db is None:
        return "disconnected"
    try:
        healthy = await asyncio.wait_for(
            db.health_check(), timeout=_HEALTH_CHECK_TIMEOUT
        )
        return "connected" if healthy else "disconnected"
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning(
            "Health check: database check failed: %s",
            exc,
            extra={"service": "database", "error": str(exc)},
        )
        return "disconnected"


async def _check_es_health() -> str:
    """Elasticsearch 연결 상태를 확인합니다.

    Returns:
        "connected" 또는 "disconnected".
    """
    from app.main import get_es

    es = get_es()
    if es is None:
        return "disconnected"
    try:
        healthy = await asyncio.wait_for(
            es.is_healthy(), timeout=_HEALTH_CHECK_TIMEOUT
        )
        return "connected" if healthy else "disconnected"
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning(
            "Health check: elasticsearch check failed: %s",
            exc,
            extra={"service": "elasticsearch", "error": str(exc)},
        )
        return "disconnected"


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """서비스 헬스체크 엔드포인트.

    Database와 Elasticsearch의 연결 상태를 동시에 확인하고 전체 서비스
    상태를 판단하여 반환합니다. 5초 이내 응답을 보장합니다.

    Returns:
        HealthResponse: status, database, elasticsearch, uptime_seconds 포함.
    """
    from app.main import get_start_time

    # DB와 ES 상태를 동시에 확인 (병렬 실행으로 응답 시간 최소화)
    db_status, es_status = await asyncio.gather(
        _check_db_health(),
        _check_es_health(),
    )

    # 전체 상태 결정
    if db_status == "connected" and es_status == "connected":
        status = "healthy"
    elif db_status == "disconnected" and es_status == "disconnected":
        status = "unhealthy"
    else:
        status = "degraded"

    # 가동 시간 계산
    uptime = time.time() - get_start_time()

    return HealthResponse(
        status=status,
        database=db_status,
        elasticsearch=es_status,
        uptime_seconds=round(uptime, 2),
    )
