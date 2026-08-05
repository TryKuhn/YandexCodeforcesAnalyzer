"""Scoreboard cache, dropped by event rather than by timeout."""
import json
from typing import Any, Protocol


class CacheBackend(Protocol):
    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, ex: int | None = None) -> Any: ...

    async def delete(self, *keys: str) -> Any: ...


def key_for(contest_id: int) -> str:
    return f"judge:scoreboard:{contest_id}"


class ScoreboardCache:
    """Thin wrapper so the routes never touch Redis directly."""

    def __init__(self, backend: CacheBackend | None, ttl_seconds: int = 60) -> None:
        self._backend = backend
        self._ttl = ttl_seconds

    async def read(self, contest_id: int) -> dict | None:
        if self._backend is None:
            return None
        raw = await self._backend.get(key_for(contest_id))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            # a corrupt entry must not break the board, just miss the cache
            return None

    async def write(self, contest_id: int, payload: dict) -> None:
        if self._backend is None:
            return
        await self._backend.set(
            key_for(contest_id), json.dumps(payload), ex=self._ttl
        )

    async def invalidate(self, contest_id: int) -> None:
        """Called when a submission is judged; the next read recomputes."""
        if self._backend is None:
            return
        await self._backend.delete(key_for(contest_id))
