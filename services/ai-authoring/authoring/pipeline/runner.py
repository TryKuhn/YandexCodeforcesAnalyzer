"""The worker: executes queued runs and keeps recently opened problems in sync.

* runs of one session never overlap (the oldest queued run of a session waits
  for the running one), runs of different sessions go in parallel;
* a run that ends with ``{"build": True}`` gets a build run chained after it;
* runs left ``running`` by a crashed worker are failed on start-up (re-running
  half of a generation blindly could surprise the user more than a clear error);
* every ``SYNC_INTERVAL_MINUTES`` problems opened within
  ``SYNC_ACTIVE_WINDOW_HOURS`` are re-read; differences become notifications.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from authoring.db import Session, utcnow
from authoring.llm.client import LLM, LLMError
from authoring.llm.client import llm as default_llm
from authoring.models import ACTIVE_RUN_STATUSES, AuthoringSession, Message, Run, RunKind, RunStatus
from authoring.pipeline.build import run_build
from authoring.pipeline.chat import run_chat
from authoring.pipeline.context import PipelineError, RunCancelled, RunContext
from authoring.pipeline.generate import run_generate, run_groups
from authoring.polygon.client import PolygonClient, PolygonError
from authoring.settings import settings
from authoring.sync.service import has_active_run, sync_session
from authoring.sync.snapshot import SnapshotError

logger = logging.getLogger(__name__)

Handler = Callable[[RunContext], Awaitable[dict]]

HANDLERS: dict[str, Handler] = {
    RunKind.CHAT.value: run_chat,
    RunKind.GENERATE.value: run_generate,
    RunKind.GROUPS.value: run_groups,
    RunKind.BUILD.value: run_build,
}

HEARTBEAT_SECONDS = 30
SCHEDULER_SECONDS = 60
SYNC_TIMEOUT_SECONDS = 120


async def enqueue(
    db: AsyncSession, session: AuthoringSession, kind: str, payload: dict | None = None,
    *, parent_run_id: str | None = None,
) -> Run:
    run = Run(
        session_id=session.id, user_id=session.user_id, kind=kind, payload=payload or {},
        parent_run_id=parent_run_id, step="В очереди",
    )
    db.add(run)
    await db.commit()
    return run


class Worker:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = Session,
        *,
        llm: LLM = default_llm,
        client_factory: Callable[[int], PolygonClient] = PolygonClient,
        concurrency: int = 4,
    ) -> None:
        self.sessions = session_factory
        self.llm = llm
        self.client_factory = client_factory
        self.concurrency = concurrency
        self._busy_sessions: set[str] = set()
        self._run_sessions: dict[str, str] = {}
        self._tasks: set[asyncio.Task] = set()
        self._last_schedule = 0.0
        self._scheduler: asyncio.Task | None = None

    # ---------------------------------------------------------------- recovery
    async def recover(self, *, all_running: bool = False) -> int:
        """Fail runs abandoned by a (previous) worker.

        At start-up (``all_running``) every ``running`` run is abandoned: there is
        one worker, and a restart within RUN_STALE_SECONDS would otherwise leave a
        run with a fresh heartbeat that blocks its problem forever. Later, runs
        with a stale heartbeat are swept periodically.
        """
        cutoff = utcnow() - timedelta(seconds=settings.RUN_STALE_SECONDS)
        async with self.sessions() as db:
            query = select(Run).where(Run.status == RunStatus.RUNNING.value)
            if not all_running:
                query = query.where(
                    or_(Run.heartbeat_at.is_(None), Run.heartbeat_at < cutoff),
                    Run.session_id.not_in(self._busy_sessions or {""}),
                )
            stale = (await db.execute(query)).scalars().all()
            for run in stale:
                run.status = RunStatus.FAILED.value
                run.error = "прервано перезапуском сервиса"
                run.finished_at = utcnow()
                db.add(Message(
                    session_id=run.session_id, role="system",
                    content="Операция прервана перезапуском сервиса. Повторите запрос.",
                    meta={"run_id": run.id, "is_error": True},
                ))
            await db.commit()
            return len(stale)

    # ---------------------------------------------------------------- claiming
    async def claim(self) -> str | None:
        """Take the oldest queued run whose session is idle."""
        async with self.sessions() as db:
            running = select(Run.session_id).where(Run.status == RunStatus.RUNNING.value)
            query = (
                select(Run)
                .where(Run.status == RunStatus.QUEUED.value, Run.session_id.not_in(running))
                .order_by(Run.created_at)
                .limit(10)
                .with_for_update(skip_locked=True)
            )
            for run in (await db.execute(query)).scalars().all():
                if run.session_id in self._busy_sessions:
                    continue
                run.status = RunStatus.RUNNING.value
                run.started_at = run.heartbeat_at = utcnow()
                await db.commit()
                self._busy_sessions.add(run.session_id)
                self._run_sessions[run.id] = run.session_id
                return run.id
            await db.rollback()
        return None

    # ---------------------------------------------------------------- execution
    async def _heartbeat(self, run_id: str) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            try:
                async with self.sessions() as db:
                    await db.execute(update(Run).where(Run.id == run_id).values(heartbeat_at=utcnow()))
                    await db.commit()
            except Exception:  # noqa: BLE001 - a missed heartbeat is not fatal
                logger.warning("heartbeat failed for run %s", run_id, exc_info=True)

    async def execute(self, run_id: str) -> None:
        heartbeat = asyncio.create_task(self._heartbeat(run_id))
        try:
            await self._execute_run(run_id)
        except Exception:  # noqa: BLE001 - never leave a run "running"
            logger.exception("run %s: unexpected failure in the runner", run_id)
            await self._force_fail(run_id)
        finally:
            heartbeat.cancel()
            self._busy_sessions.discard(self._run_sessions.pop(run_id, ""))

    async def _force_fail(self, run_id: str) -> None:
        try:
            async with self.sessions() as db:
                await db.execute(
                    update(Run)
                    .where(Run.id == run_id, Run.status == RunStatus.RUNNING.value)
                    .values(status=RunStatus.FAILED.value, error="внутренняя ошибка", finished_at=utcnow(),
                            step="Ошибка")
                )
                await db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("run %s: could not mark it failed", run_id)

    async def _execute_run(self, run_id: str) -> None:
        async with self.sessions() as db:
            run = await db.get(Run, run_id)
            if run is None:
                return
            session = await db.get(AuthoringSession, run.session_id)
            if session is None:
                return
            ctx = RunContext(db=db, run=run, session=session, client=self.client_factory(run.user_id),
                             llm=self.llm)
            await self._execute(ctx)

    async def _execute(self, ctx: RunContext) -> None:
        run, db = ctx.run, ctx.db
        run_id, kind, session_id, user_id = run.id, run.kind, run.session_id, run.user_id
        handler = HANDLERS.get(kind)
        error_text: str | None = None
        status = RunStatus.DONE.value
        result: dict = {}
        try:
            if handler is None:
                raise PipelineError(f"неизвестный тип операции: {kind}")
            result = await handler(ctx) or {}
            if result.get("needs_user"):
                status = RunStatus.NEEDS_USER.value
        except RunCancelled:
            await db.rollback()
            status, error_text = RunStatus.CANCELLED.value, "отменено пользователем"
            await self._say(ctx, "Операция отменена.", role="system")
        except PipelineError as e:
            await db.rollback()
            status, error_text = RunStatus.FAILED.value, str(e)
            await self._say(ctx, f"Не получилось: {e}", is_error=True)
        except LLMError as e:
            await db.rollback()
            status, error_text = RunStatus.FAILED.value, e.message
            await self._say(ctx, f"Ошибка модели: {e.message}", is_error=True)
        except (PolygonError, SnapshotError) as e:
            await db.rollback()
            message = getattr(e, "message", str(e))
            status, error_text = RunStatus.FAILED.value, message
            await self._say(ctx, f"Ошибка Polygon: {message}", is_error=True)
        except Exception as e:  # noqa: BLE001 - the run must end with a status
            logger.exception("run %s (%s) crashed", run_id, kind)
            await db.rollback()
            status, error_text = RunStatus.FAILED.value, f"{type(e).__name__}: {e}"
            await self._say(ctx, "Внутренняя ошибка сервиса, подробности в логах.", is_error=True)

        # the problem may have changed (even by a run that failed half-way): refresh
        # the snapshot quietly so the next sync does not report our own edits
        if kind != RunKind.CHAT.value or result.get("changed") or status != RunStatus.DONE.value:
            try:
                await db.refresh(ctx.session)  # expired by a rollback above
                await sync_session(db, ctx.session, ctx.client, announce=False)
            except Exception:  # noqa: BLE001 - best effort
                await db.rollback()
                logger.info("run %s: final snapshot refresh failed", run_id, exc_info=True)

        await db.execute(
            update(Run).where(Run.id == run_id).values(
                status=status,
                error=error_text,
                result=result,
                finished_at=utcnow(),
                step={"done": "Готово", "needs_user": "Нужна помощь", "cancelled": "Отменено"}.get(status, "Ошибка"),
            )
        )
        await db.commit()

        session = await db.get(AuthoringSession, session_id)
        auto_build = bool((session.settings or {}).get("auto_build", True)) if session else False
        wants_build = result.get("build") and (auto_build or result.get("force_build"))
        if status == RunStatus.DONE.value and wants_build and kind != RunKind.BUILD.value:
            already = await db.scalar(
                select(Run.id).where(
                    Run.session_id == session_id,
                    Run.kind == RunKind.BUILD.value,
                    Run.status == RunStatus.QUEUED.value,
                ).limit(1)
            )
            if already is None:
                db.add(Run(
                    session_id=session_id, user_id=user_id, kind=RunKind.BUILD.value,
                    payload={"reason": kind}, parent_run_id=run_id, step="В очереди",
                ))
                await db.commit()

    @staticmethod
    async def _say(ctx: RunContext, text: str, **kwargs: object) -> None:
        try:
            await ctx.say(text, **kwargs)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 - reporting must not break the status write
            await ctx.db.rollback()
            logger.exception("run %s: could not post a message", ctx.run_id)

    # ---------------------------------------------------------------- sync
    async def scheduler_tick(self) -> int:
        """Sync problems that were opened recently and not synced for a while."""
        now = utcnow()
        async with self.sessions() as db:
            due = (await db.execute(
                select(AuthoringSession).where(
                    AuthoringSession.last_opened_at >= now - timedelta(hours=settings.SYNC_ACTIVE_WINDOW_HOURS),
                    or_(
                        AuthoringSession.last_synced_at.is_(None),
                        AuthoringSession.last_synced_at < now - timedelta(minutes=settings.SYNC_INTERVAL_MINUTES),
                    ),
                ).limit(50)
            )).scalars().all()
            synced = 0
            for session in due:
                if session.id in self._busy_sessions or await has_active_run(db, session.id):
                    continue
                try:
                    await asyncio.wait_for(
                        sync_session(db, session, self.client_factory(session.user_id), announce=True),
                        timeout=SYNC_TIMEOUT_SECONDS,
                    )
                    synced += 1
                except (TimeoutError, SnapshotError, PolygonError) as e:
                    await db.rollback()
                    logger.info("background sync of %s failed: %s", session.id, e)
                    session.last_synced_at = utcnow()  # do not hammer a broken problem
                    await db.commit()
            return synced

    async def _background(self) -> None:
        try:
            await self.recover()
            await self.scheduler_tick()
        except Exception:  # noqa: BLE001
            logger.exception("background sync failed")

    # ---------------------------------------------------------------- loop
    async def run_forever(self, stop: asyncio.Event | None = None) -> None:
        stop = stop or asyncio.Event()
        recovered = await self.recover(all_running=True)
        logger.info("ai worker started (recovered %d stale runs)", recovered)
        loop = asyncio.get_running_loop()
        while not stop.is_set():
            try:
                while len(self._tasks) < self.concurrency:
                    run_id = await self.claim()
                    if run_id is None:
                        break
                    task = asyncio.create_task(self.execute(run_id))
                    self._tasks.add(task)
                    task.add_done_callback(self._tasks.discard)
                # sync + stale sweep in the background: a slow Polygon must not
                # delay picking up new chat messages
                if loop.time() - self._last_schedule >= SCHEDULER_SECONDS and (
                    self._scheduler is None or self._scheduler.done()
                ):
                    self._last_schedule = loop.time()
                    self._scheduler = asyncio.create_task(self._background())
            except Exception:  # noqa: BLE001 - keep the worker alive
                logger.exception("worker loop error")
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.WORKER_POLL_SECONDS)
            except TimeoutError:
                pass
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)


async def has_queued_or_running(db: AsyncSession, session_id: str) -> Run | None:
    return (await db.execute(
        select(Run).where(Run.session_id == session_id, Run.status.in_(ACTIVE_RUN_STATUSES))
        .order_by(Run.created_at).limit(1)
    )).scalars().first()
