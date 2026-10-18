"""Synchronization of a session with Polygon: snapshot, diff, notification."""
from __future__ import annotations

import logging

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from authoring.db import utcnow
from authoring.models import ACTIVE_RUN_STATUSES, AuthoringSession, Event, Run, Snapshot
from authoring.polygon.client import PolygonClient
from authoring.sync.diff import diff, summarize
from authoring.sync.snapshot import SnapshotError, take_snapshot

logger = logging.getLogger(__name__)


async def has_active_run(db: AsyncSession, session_id: str) -> bool:
    found = await db.scalar(
        select(Run.id).where(Run.session_id == session_id, Run.status.in_(ACTIVE_RUN_STATUSES)).limit(1)
    )
    return found is not None


async def load_snapshot(db: AsyncSession, session_id: str) -> dict | None:
    row = await db.get(Snapshot, session_id)
    return row.data if row else None


async def sync_session(
    db: AsyncSession,
    session: AuthoringSession,
    client: PolygonClient,
    *,
    announce: bool = True,
) -> tuple[dict, Event | None]:
    """Take a fresh snapshot and store it.

    With ``announce`` the differences from the previous snapshot become an
    :class:`Event` (changes made on Polygon behind our back). The service's own
    runs refresh with ``announce=False``: they report their changes themselves.
    """
    session_id = session.id
    row = await db.get(Snapshot, session_id)
    previous = row.data if row else None
    try:
        snapshot = await take_snapshot(client, session.polygon_id, previous)
    except SnapshotError as e:
        session.sync_error = e.message
        await db.commit()
        raise

    event: Event | None = None
    if previous and announce:
        changes = diff(previous, snapshot)
        if changes:
            event = Event(
                session_id=session.id, source="polygon", title=summarize(changes), changes=changes
            )
            db.add(event)

    if row is None:
        db.add(Snapshot(session_id=session.id, data=snapshot, taken_at=utcnow()))
    else:
        row.data = snapshot
        row.taken_at = utcnow()
    session.last_synced_at = utcnow()
    session.sync_error = "; ".join(snapshot.get("errors") or [])[:2000] or None
    try:
        await db.commit()
    except IntegrityError:
        # a concurrent first sync inserted the row: overwrite it instead
        await db.rollback()
        await db.execute(
            update(Snapshot).where(Snapshot.session_id == session_id).values(data=snapshot, taken_at=utcnow())
        )
        await db.commit()
        event = None
    return snapshot, event
