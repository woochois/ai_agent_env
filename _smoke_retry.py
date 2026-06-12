import asyncio
from unittest.mock import AsyncMock, patch

from app.services.retry import connect_with_retry


async def main():
    # Case 1: sync fn always fails -> exactly max_retries attempts, None result
    calls = {"n": 0}

    def fail_sync():
        calls["n"] += 1
        raise ConnectionError("boom")

    with patch("app.services.retry.asyncio.sleep", new=AsyncMock()) as sleep_mock:
        res = await connect_with_retry(fail_sync, "database", max_retries=3, interval_seconds=5.0)
    assert res is None, res
    assert calls["n"] == 3, calls["n"]
    # sleeps between attempts only: 2 sleeps for 3 attempts
    assert sleep_mock.await_count == 2, sleep_mock.await_count
    sleep_mock.assert_awaited_with(5.0)
    print("Case 1 ok: attempts=3, sleeps=2, result=None")

    # Case 2: async fn succeeds on 2nd attempt
    state = {"n": 0}

    async def succeed_second():
        state["n"] += 1
        if state["n"] < 2:
            raise ConnectionError("not yet")
        return "conn"

    with patch("app.services.retry.asyncio.sleep", new=AsyncMock()) as sleep_mock:
        res = await connect_with_retry(succeed_second, "elasticsearch", max_retries=3, interval_seconds=5.0)
    assert res == "conn", res
    assert state["n"] == 2, state["n"]
    assert sleep_mock.await_count == 1, sleep_mock.await_count
    print("Case 2 ok: success on attempt 2, sleeps=1")

    # Case 3: sync success on first attempt -> no sleeps
    with patch("app.services.retry.asyncio.sleep", new=AsyncMock()) as sleep_mock:
        res = await connect_with_retry(lambda: "ok", "database")
    assert res == "ok", res
    assert sleep_mock.await_count == 0
    print("Case 3 ok: immediate success, sleeps=0")


asyncio.run(main())
print("ALL SMOKE TESTS PASSED")
