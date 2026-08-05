"""Locking so two workers never build the same problem at once."""
import asyncio
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class LockBusy(RuntimeError):
    """Somebody else is already building this problem."""


class BuildLock(ABC):
    @asynccontextmanager
    @abstractmethod
    async def hold(self, key: str, *, ttl_ms: int = 600_000) -> AsyncIterator[None]:
        """Hold the lock for the duration of a build."""
        raise NotImplementedError
        yield  # pragma: no cover


class LocalBuildLock(BuildLock):
    """Single-process lock, enough while the judge runs as one service."""

    def __init__(self) -> None:
        self._held: set[str] = set()

    @asynccontextmanager
    async def hold(self, key: str, *, ttl_ms: int = 600_000) -> AsyncIterator[None]:
        if key in self._held:
            raise LockBusy(f"problem {key} is already being built")
        self._held.add(key)
        try:
            yield
        finally:
            self._held.discard(key)


class RedisBuildLock(BuildLock):
    """Redlock-style lock: SET NX with a TTL, released only by its owner.

    The TTL is what makes it safe -- a worker that dies mid-build cannot leave
    the problem locked forever.
    """

    # releasing by value stops us from dropping a lock the TTL already gave away
    _RELEASE = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    end
    return 0
    """

    def __init__(self, redis) -> None:
        self._redis = redis

    @asynccontextmanager
    async def hold(self, key: str, *, ttl_ms: int = 600_000) -> AsyncIterator[None]:
        token = uuid.uuid4().hex
        name = f"judge:build:{key}"
        acquired = await self._redis.set(name, token, nx=True, px=ttl_ms)
        if not acquired:
            raise LockBusy(f"problem {key} is already being built elsewhere")
        try:
            yield
        finally:
            try:
                await self._redis.eval(self._RELEASE, 1, name, token)
            except Exception:
                # the TTL will clean up; failing to unlock must not fail the build
                await asyncio.sleep(0)
