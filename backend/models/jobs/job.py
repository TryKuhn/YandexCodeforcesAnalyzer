"""Durable background job; the DB row is the source of truth, Redis only wakes workers."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, utcnow


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Job(Base):
    """One background job: type picks the handler, payload/result are JSON."""
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(
        String(16), default=JobStatus.QUEUED.value, index=True
    )
    progress: Mapped[int] = mapped_column(default=0)
    attempts: Mapped[int] = mapped_column(default=0)

    # flat id on purpose: jobs are infra and must not grow FKs into domain tables
    user_id: Mapped[int | None] = mapped_column(nullable=True)

    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
