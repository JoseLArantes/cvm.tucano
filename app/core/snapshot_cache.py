import asyncio
from collections.abc import Awaitable, Callable, Hashable
from copy import deepcopy
from threading import Lock
from time import monotonic
from typing import Any, TypeVar, cast

T = TypeVar("T")


class SnapshotCache:
    """Cacheia snapshots curtos e compartilha calculos simultaneos sem bloquear threads."""

    def __init__(self, *, max_entries: int = 128) -> None:
        self._max_entries = max_entries
        self._lock = Lock()
        self._entries: dict[Hashable, tuple[float, Any]] = {}
        self._inflight: dict[Hashable, asyncio.Future[Any]] = {}

    async def get_or_compute(
        self,
        key: Hashable,
        ttl_seconds: float,
        factory: Callable[[], Awaitable[T]],
    ) -> T:
        if ttl_seconds <= 0:
            return await factory()

        now = monotonic()
        cached_value: Any = None
        found = False
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and entry[0] > now:
                cached_value = entry[1]
                found = True
                future = None
                is_owner = False
            else:
                future = self._inflight.get(key)
                is_owner = future is None
                if future is None:
                    future = asyncio.get_running_loop().create_future()
                    future.add_done_callback(self._consume_future_exception)
                    self._inflight[key] = future

        if found:
            return cast(T, deepcopy(cached_value))
        if not is_owner:
            assert future is not None
            return cast(T, deepcopy(await asyncio.shield(future)))
        assert future is not None

        try:
            value = await factory()
            snapshot = deepcopy(value)
        except BaseException as exc:
            with self._lock:
                self._inflight.pop(key, None)
            if not future.done():
                future.set_exception(exc)
            raise

        with self._lock:
            self._entries[key] = (monotonic() + ttl_seconds, snapshot)
            self._inflight.pop(key, None)
            self._prune_expired(monotonic())
        future.set_result(snapshot)
        return deepcopy(snapshot)

    @staticmethod
    def _consume_future_exception(future: asyncio.Future[Any]) -> None:
        if not future.cancelled():
            future.exception()

    def _prune_expired(self, now: float) -> None:
        expired = [key for key, (expires_at, _) in self._entries.items() if expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)
        while len(self._entries) > self._max_entries:
            self._entries.pop(next(iter(self._entries)))
