"""ORM models of the AI authoring service (all tables are ``authoring_*``)."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from authoring.db import Base, utcnow


def new_id() -> str:
    return str(uuid.uuid4())


class ProblemType(str, enum.Enum):
    REGULAR = "regular"
    INTERACTIVE = "interactive"
    OUTPUT_ONLY = "output_only"


class RunKind(str, enum.Enum):
    CHAT = "chat"          # one chat message: route, then answer or edit
    GENERATE = "generate"  # a whole problem from an idea
    GROUPS = "groups"      # groups/points plan -> generators, script, scoring
    BUILD = "build"        # package build with automatic repair


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    NEEDS_USER = "needs_user"  # gave up (e.g. the build is still red after the repairs)
    CANCELLED = "cancelled"


ACTIVE_RUN_STATUSES = (RunStatus.QUEUED.value, RunStatus.RUNNING.value)


class AuthoringSession(Base):
    """The AI workspace of one user for one Polygon problem."""

    __tablename__ = "authoring_sessions"
    __table_args__ = (UniqueConstraint("user_id", "polygon_id", name="uq_authoring_session"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    polygon_id: Mapped[int] = mapped_column(Integer, index=True)
    problem_type: Mapped[str] = mapped_column(String(16), default=ProblemType.REGULAR.value)
    model: Mapped[str] = mapped_column(String(128))
    # auto_build, groups_plan, ... (see api.schemas.SessionSettings)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    last_opened_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Message(Base):
    """A chat message; ``meta`` carries the intent, changed files, run id, ..."""

    __tablename__ = "authoring_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("authoring_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Snapshot(Base):
    """The last known state of the problem on Polygon (one row per session)."""

    __tablename__ = "authoring_snapshots"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("authoring_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    taken_at: Mapped[datetime] = mapped_column(default=utcnow)


class Event(Base):
    """A notification for the user: what changed in the problem, a finished build, ..."""

    __tablename__ = "authoring_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("authoring_sessions.id", ondelete="CASCADE"), index=True
    )
    # polygon: changed on Polygon by someone else; ai: changed by this service;
    # build: package builds
    source: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(Text)
    changes: Mapped[list] = mapped_column(JSON, default=list)
    seen: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Run(Base):
    """A unit of background work executed by the worker, one at a time per session."""

    __tablename__ = "authoring_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("authoring_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default=RunStatus.QUEUED.value, index=True)
    step: Mapped[str] = mapped_column(Text, default="")
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Build(Base):
    """One package build attempt (a build run makes 1 + up to N repair attempts)."""

    __tablename__ = "authoring_builds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("authoring_sessions.id", ondelete="CASCADE"), index=True
    )
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    package_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # STARTING, PENDING, RUNNING, READY, FAILED, TIMEOUT, ERROR
    state: Mapped[str] = mapped_column(String(16), default="STARTING")
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
