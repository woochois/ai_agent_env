"""Elasticsearch 클라이언트 모듈.

ELASTICSEARCH_URL 환경 변수를 사용하여 Elasticsearch 비동기 클라이언트를
초기화하고, ``connect_with_retry``를 적용하여 연결 실패 시 재시도합니다.
또한 헬스체크용 연결 상태 확인 메서드를 제공합니다.

연결 상태 판단 기준 (Requirement 5.7): 클러스터 상태 API(_cluster/health)의
status가 ``green`` 또는 ``yellow``이면 정상으로 간주합니다.

Requirements: 5.3, 5.4, 5.5
"""

from __future__ import annotations

import logging
from typing import Optional

from elasticsearch import AsyncElasticsearch

from app.config import get_settings
from app.services.retry import connect_with_retry

logger = logging.getLogger(__name__)

# 정상으로 판단할 클러스터 상태 값
HEALTHY_CLUSTER_STATUSES = {"green", "yellow"}


class ElasticsearchClient:
    """Elasticsearch 비동기 클라이언트 래퍼.

    ELASTICSEARCH_URL로 ``AsyncElasticsearch`` 클라이언트를 구성하고,
    ``connect_with_retry``를 통해 연결을 시도합니다. 연결 상태 확인 메서드를
    제공하여 헬스체크에 활용할 수 있습니다.

    Attributes:
        url: Elasticsearch 연결 URL.
        client: 초기화된 ``AsyncElasticsearch`` 인스턴스. ``connect`` 호출 전에는 None.
    """

    def __init__(self, url: Optional[str] = None) -> None:
        """클라이언트 래퍼를 초기화합니다.

        Args:
            url: Elasticsearch 연결 URL. 생략하면 설정(ELASTICSEARCH_URL)에서 가져옵니다.
        """
        self.url: str = url if url is not None else get_settings().ELASTICSEARCH_URL
        self.client: Optional[AsyncElasticsearch] = None

    async def connect(
        self,
        max_retries: int = 3,
        interval_seconds: float = 5.0,
    ) -> Optional[AsyncElasticsearch]:
        """재시도 로직을 적용하여 Elasticsearch에 연결합니다.

        ``connect_with_retry``를 사용하여 최대 ``max_retries``회, 각 시도 사이에
        ``interval_seconds``초 간격으로 연결을 시도합니다. 연결 확인은
        클러스터 ping을 통해 수행하며, 모든 시도가 실패하면 에러가 로깅되고
        ``client``는 None으로 유지됩니다.

        Args:
            max_retries: 최대 시도 횟수. 기본값 3.
            interval_seconds: 각 시도 사이의 대기 시간(초). 기본값 5.0.

        Returns:
            연결에 성공하면 ``AsyncElasticsearch`` 인스턴스, 실패하면 None.
        """

        async def _connect() -> AsyncElasticsearch:
            client = AsyncElasticsearch(hosts=[self.url])
            # ping이 False를 반환하거나 예외가 발생하면 재시도 대상으로 처리
            if not await client.ping():
                await client.close()
                raise ConnectionError(
                    f"Elasticsearch ping failed for {self.url}"
                )
            return client

        self.client = await connect_with_retry(
            _connect,
            service_name="elasticsearch",
            max_retries=max_retries,
            interval_seconds=interval_seconds,
        )
        return self.client

    async def is_healthy(self) -> bool:
        """Elasticsearch 연결 및 클러스터 상태를 확인합니다 (헬스체크용).

        클러스터 상태 API(_cluster/health)를 호출하여 status가 ``green`` 또는
        ``yellow``이면 정상(True)으로 판단합니다. 클라이언트가 초기화되지 않았거나
        호출 중 예외가 발생하면 비정상(False)으로 처리합니다.

        Returns:
            클러스터 상태가 정상이면 True, 그렇지 않으면 False.
        """
        if self.client is None:
            logger.warning(
                "Elasticsearch health check called before client initialization",
                extra={"service": "elasticsearch"},
            )
            return False

        try:
            health = await self.client.cluster.health()
            status = health.get("status")
            is_healthy = status in HEALTHY_CLUSTER_STATUSES
            if not is_healthy:
                logger.warning(
                    "Elasticsearch cluster status is unhealthy: %s",
                    status,
                    extra={"service": "elasticsearch", "status": status},
                )
            return is_healthy
        except Exception as exc:  # noqa: BLE001 - 헬스체크 실패는 unhealthy로 간주
            logger.error(
                "Elasticsearch health check failed: %s",
                exc,
                extra={"service": "elasticsearch", "error": str(exc)},
            )
            return False

    async def close(self) -> None:
        """Elasticsearch 클라이언트 연결을 종료합니다."""
        if self.client is not None:
            await self.client.close()
            self.client = None
