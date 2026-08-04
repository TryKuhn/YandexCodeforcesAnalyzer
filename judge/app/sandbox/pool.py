"""Leasing of isolate box ids, which also caps how many runs go at once."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

MAX_BOX_ID = 999


class BoxCorrupted(RuntimeError):
    """A box could not be cleaned and must not be reused."""


class BoxPool:
    """Hands out box ids, one holder at a time."""

    def __init__(self, size: int, first_id: int = 0) -> None:
        if size < 1:
            raise ValueError("pool size must be at least 1")
        if first_id < 0 or first_id + size - 1 > MAX_BOX_ID:
            raise ValueError(f"box ids must stay within 0..{MAX_BOX_ID}")

        self._ids = list(range(first_id, first_id + size))
        self._free: asyncio.Queue[int] = asyncio.Queue()
        for box_id in self._ids:
            self._free.put_nowait(box_id)
        self._broken: set[int] = set()

    @property
    def size(self) -> int:
        return len(self._ids)

    @property
    def available(self) -> int:
        return self._free.qsize()

    @property
    def broken(self) -> frozenset[int]:
        return frozenset(self._broken)

    @asynccontextmanager
    async def lease(self) -> AsyncIterator[int]:
        """Borrow a box id, blocking while every box is busy."""
        box_id = await self._free.get()
        keep = True
        try:
            yield box_id
        except BoxCorrupted:
            keep = False
            raise
        finally:
            if keep:
                self._free.put_nowait(box_id)
            else:
                self._broken.add(box_id)

    def retire(self, box_id: int) -> None:
        """Drop a box from circulation without returning it."""
        self._broken.add(box_id)
