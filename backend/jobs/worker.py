"""Worker loop: pulls job ids, runs registered handlers, records outcomes."""
import asyncio
import logging
import socket
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from . import queue
from .transport import Transport

logger = logging.getLogger(__name__)

# handler(payload, progress) -> result dict; progress takes 0..100
Handler = Callable[[dict, Callable[[int], Awaitable[None]]], Awaitable[dict | None]]


class Worker:
    def __init__(
        self,
        transport: Transport,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        handlers: dict[str, Handler] | None = None,
        consumer: str | None = None,
        max_attempts: int = 3,
        reclaim_idle_ms: int = 60_000,
    ) -> None:
        self._transport = transport
        self._sessions = session_factory
        self._handlers: dict[str, Handler] = dict(handlers or {})
        self._consumer = consumer or f"{socket.gethostname()}-{uuid.uuid4().hex[:6]}"
        self._max_attempts = max_attempts
        self._reclaim_idle_ms = reclaim_idle_ms

    def register(self, job_type: str, handler: Handler) -> None:
        if job_type in self._handlers:
            raise ValueError(f"handler already registered: {job_type}")
        self._handlers[job_type] = handler

    async def run_once(self, *, block_ms: int = 5000) -> int:
        """One pass: recover abandoned entries, then take fresh ones."""
        processed = 0
        for entry_id, job_id in await self._transport.reclaim(
            self._consumer, self._reclaim_idle_ms
        ):
            await self._process(entry_id, job_id, reclaimed=True)
            processed += 1
        for entry_id, job_id in await self._transport.pull(self._consumer, block_ms=block_ms):
            await self._process(entry_id, job_id)
            processed += 1
        return processed

    async def run(self, stop: asyncio.Event | None = None) -> None:
        logger.info("job worker started: consumer=%s", self._consumer)
        while stop is None or not stop.is_set():
            try:
                await self.run_once()
            except Exception:
                # transport hiccups must not kill the worker
                logger.exception("worker loop error")
                await asyncio.sleep(1)

    async def _process(self, entry_id: str, job_id: str, *, reclaimed: bool = False) -> None:
        async with self._sessions() as db:
            job = await queue.claim(db, uuid.UUID(job_id), reclaim=reclaimed)
            if job is None:
                # someone else already took or finished it
                await self._transport.ack(entry_id)
                return

            handler = self._handlers.get(job.type)
            if handler is None:
                # no retry: a handler will not appear by itself
                job.attempts = self._max_attempts
                await queue.fail(db, job, f"no handler for job type: {job.type}",
                                 max_attempts=self._max_attempts)
                await self._transport.ack(entry_id)
                return

            async def progress(percent: int) -> None:
                await queue.set_progress(db, job, percent)

            try:
                result = await handler(job.payload, progress)
                await queue.complete(db, job, result or {})
            except Exception as exc:
                logger.exception("job %s (%s) failed", job.id, job.type)
                retry = await queue.fail(
                    db, job, f"{type(exc).__name__}: {exc}", max_attempts=self._max_attempts
                )
                if retry:
                    await self._transport.push(str(job.id))
            await self._transport.ack(entry_id)
