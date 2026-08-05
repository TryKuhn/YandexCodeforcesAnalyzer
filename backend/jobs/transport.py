"""How enqueue wakes workers; the jobs table stays the source of truth."""
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import ResponseError

STREAM = "jobs:stream"
GROUP = "workers"


class Transport(Protocol):
    """Delivery of job ids; entries are (entry_id, job_id) pairs."""

    async def push(self, job_id: str) -> None: ...

    async def pull(
        self, consumer: str, count: int = 8, block_ms: int = 5000
    ) -> list[tuple[str, str]]: ...

    async def ack(self, entry_id: str) -> None: ...

    async def reclaim(
        self, consumer: str, min_idle_ms: int = 60_000, count: int = 8
    ) -> list[tuple[str, str]]: ...


class RedisStreamTransport:
    """Redis Streams with a consumer group, so a dead worker's entries get reclaimed."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._group_ready = False

    async def _ensure_group(self) -> None:
        if self._group_ready:
            return
        try:
            # id="0" so entries pushed before the group existed are still delivered
            await self._redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        self._group_ready = True

    async def push(self, job_id: str) -> None:
        await self._redis.xadd(STREAM, {"job": job_id})

    async def pull(
        self, consumer: str, count: int = 8, block_ms: int = 5000
    ) -> list[tuple[str, str]]:
        await self._ensure_group()
        response = await self._redis.xreadgroup(
            GROUP, consumer, {STREAM: ">"}, count=count, block=block_ms
        )
        if not response:
            return []
        _, entries = response[0]
        return [(entry_id, fields["job"]) for entry_id, fields in entries]

    async def ack(self, entry_id: str) -> None:
        await self._redis.xack(STREAM, GROUP, entry_id)

    async def reclaim(
        self, consumer: str, min_idle_ms: int = 60_000, count: int = 8
    ) -> list[tuple[str, str]]:
        await self._ensure_group()
        _, entries, _ = await self._redis.xautoclaim(
            STREAM, GROUP, consumer, min_idle_time=min_idle_ms, count=count
        )
        return [(entry_id, fields["job"]) for entry_id, fields in entries]
