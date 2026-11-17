import asyncio

import pytest

from app.core.snapshot_cache import SnapshotCache


def test_snapshot_cache_reuses_value_until_ttl_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    current_time = [10.0]
    monkeypatch.setattr("app.core.snapshot_cache.monotonic", lambda: current_time[0])
    cache = SnapshotCache()
    calls = 0

    async def factory() -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"value": calls}

    async def exercise() -> None:
        assert await cache.get_or_compute("snapshot", 3, factory) == {"value": 1}
        current_time[0] = 12.9
        assert await cache.get_or_compute("snapshot", 3, factory) == {"value": 1}
        current_time[0] = 13.0
        assert await cache.get_or_compute("snapshot", 3, factory) == {"value": 2}

    asyncio.run(exercise())
    assert calls == 2


def test_snapshot_cache_computes_a_key_once_for_concurrent_misses() -> None:
    cache = SnapshotCache()
    calls = 0

    async def factory() -> dict[str, int]:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return {"value": 42}

    async def exercise() -> None:
        values = await asyncio.gather(*(cache.get_or_compute("snapshot", 3, factory) for _ in range(8)))
        assert values == [{"value": 42}] * 8

    asyncio.run(exercise())
    assert calls == 1
