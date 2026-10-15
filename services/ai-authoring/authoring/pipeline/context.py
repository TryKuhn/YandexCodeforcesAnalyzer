"""What a run handler works with: DB, Polygon, the LLM, progress and messages."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from authoring.db import utcnow
from authoring.llm.client import LLM
from authoring.llm.models import normalize_model
from authoring.models import AuthoringSession, Event, Message, Run
from authoring.polygon.client import PolygonClient
from authoring.sync.dossier import build_dossier
from authoring.sync.service import load_snapshot, sync_session


class RunCancelled(Exception):
    """The user cancelled the run."""


class PipelineError(Exception):
    """An expected failure with a message for the user."""


@dataclass
class RunContext:
    db: AsyncSession
    run: Run
    session: AuthoringSession
    client: PolygonClient
    llm: LLM
    _snapshot: dict | None = field(default=None, repr=False)
    _stale: bool = field(default=False, repr=False)
    # plain copies: after a rollback the ORM objects are expired, and reading an
    # expired attribute would need I/O
    session_id: str = field(init=False)
    run_id: str = field(init=False)

    def __post_init__(self) -> None:
        self.session_id = self.session.id
        self.run_id = self.run.id

    # ------------------------------------------------------------ progress
    @property
    def auto_build(self) -> bool:
        return bool((self.session.settings or {}).get("auto_build", True))

    @property
    def model(self) -> str:
        return normalize_model(self.session.model)

    async def step(self, text: str, *, done: int | None = None, total: int | None = None) -> None:
        """Report progress (and fail fast when the user cancelled)."""
        await self.db.refresh(self.run, attribute_names=["cancel_requested"])
        if self.run.cancel_requested:
            raise RunCancelled()
        self.run.step = text
        if done is not None:
            self.run.progress_done = done
        if total is not None:
            self.run.progress_total = total
        self.run.heartbeat_at = utcnow()
        await self.db.commit()

    async def heartbeat(self) -> None:
        self.run.heartbeat_at = utcnow()
        await self.db.commit()

    # ------------------------------------------------------------ messages
    async def say(self, content: str, *, role: str = "assistant", **meta: object) -> Message:
        message = Message(session_id=self.session_id, role=role, content=content, meta={"run_id": self.run_id, **meta})
        self.db.add(message)
        await self.db.commit()
        return message

    async def notify(self, source: str, title: str, changes: list[dict] | None = None) -> Event:
        event = Event(session_id=self.session_id, source=source, title=title, changes=changes or [])
        self.db.add(event)
        await self.db.commit()
        return event

    async def history(self, limit: int = 12, *, before_id: int | None = None) -> list[dict]:
        query = select(Message).where(Message.session_id == self.session_id, Message.role != "system")
        if before_id is not None:
            query = query.where(Message.id < before_id)
        rows = (await self.db.execute(query.order_by(Message.id.desc()).limit(limit))).scalars().all()
        return [{"role": m.role, "content": m.content} for m in reversed(rows)]

    # ------------------------------------------------------------ problem state
    async def snapshot(self, *, refresh: bool = False, announce: bool = False) -> dict:
        """The problem state; ``refresh`` re-reads Polygon (incrementally)."""
        must_read = refresh or self._stale
        if self._snapshot is None and not must_read:
            self._snapshot = await load_snapshot(self.db, self.session_id)
        if must_read or self._snapshot is None:
            self._snapshot, _ = await sync_session(self.db, self.session, self.client, announce=announce)
            self._stale = False
        return self._snapshot

    async def dossier(self, *, refresh: bool = False) -> str:
        snapshot = await self.snapshot(refresh=refresh)
        return build_dossier(snapshot, polygon_id=self.session.polygon_id, problem_type=self.session.problem_type)

    def invalidate(self) -> None:
        """The problem was changed: the next :meth:`snapshot` re-reads Polygon."""
        self._stale = True
