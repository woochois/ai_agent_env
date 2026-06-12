"""Elasticsearch 클라이언트 단위 테스트.

ElasticsearchClient의 연결(재시도 적용) 및 헬스체크 로직을 검증합니다.
실제 Elasticsearch 서버 없이 가벼운 가짜(fake) 클라이언트로 동작을 테스트합니다.

Requirements: 5.3, 5.4, 5.5
"""

import pytest

from app.services.elasticsearch import ElasticsearchClient


class _FakeES:
    """테스트용 가짜 AsyncElasticsearch."""

    def __init__(self, *, ping_ok=True, status="green", raise_on_health=False):
        self._ping_ok = ping_ok
        self._status = status
        self._raise_on_health = raise_on_health
        self.closed = False

        outer = self

        class _Cluster:
            async def health(self):
                if outer._raise_on_health:
                    raise ConnectionError("boom")
                return {"status": outer._status}

        self.cluster = _Cluster()

    async def ping(self):
        return self._ping_ok

    async def close(self):
        self.closed = True


def test_init_uses_explicit_url():
    client = ElasticsearchClient(url="http://es:9200")
    assert client.url == "http://es:9200"
    assert client.client is None


@pytest.mark.asyncio
async def test_connect_success(monkeypatch):
    fake = _FakeES(ping_ok=True)
    monkeypatch.setattr(
        "app.services.elasticsearch.AsyncElasticsearch",
        lambda *a, **k: fake,
    )

    client = ElasticsearchClient(url="http://es:9200")
    result = await client.connect(max_retries=1, interval_seconds=0)

    assert result is fake
    assert client.client is fake


@pytest.mark.asyncio
async def test_connect_failure_returns_none(monkeypatch):
    # ping이 False면 ConnectionError를 발생시켜 재시도 후 None 반환
    fake = _FakeES(ping_ok=False)
    monkeypatch.setattr(
        "app.services.elasticsearch.AsyncElasticsearch",
        lambda *a, **k: fake,
    )

    client = ElasticsearchClient(url="http://es:9200")
    result = await client.connect(max_retries=2, interval_seconds=0)

    assert result is None
    assert client.client is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,expected",
    [("green", True), ("yellow", True), ("red", False)],
)
async def test_is_healthy_status(status, expected):
    client = ElasticsearchClient(url="http://es:9200")
    client.client = _FakeES(status=status)
    assert await client.is_healthy() is expected


@pytest.mark.asyncio
async def test_is_healthy_without_client():
    client = ElasticsearchClient(url="http://es:9200")
    assert await client.is_healthy() is False


@pytest.mark.asyncio
async def test_is_healthy_handles_exception():
    client = ElasticsearchClient(url="http://es:9200")
    client.client = _FakeES(raise_on_health=True)
    assert await client.is_healthy() is False


@pytest.mark.asyncio
async def test_close_resets_client():
    client = ElasticsearchClient(url="http://es:9200")
    fake = _FakeES()
    client.client = fake
    await client.close()
    assert fake.closed is True
    assert client.client is None
