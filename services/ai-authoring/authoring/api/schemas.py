"""Request bodies and response serializers of the HTTP API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from authoring.models import AuthoringSession, Build, Event, Message, ProblemType, Run

PROBLEM_TYPES = tuple(t.value for t in ProblemType)


class ChatContext(BaseModel):
    scope: Literal["task", "statement", "file"] = "task"
    file: str | None = None
    file_role: str | None = None


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    context: ChatContext | None = None


class SessionPatch(BaseModel):
    model: str | None = None
    problem_type: Literal["regular", "interactive", "output_only"] | None = None
    auto_build: bool | None = None


class GenerateIn(BaseModel):
    idea: str = Field(min_length=1, max_length=20000)
    plan: dict | None = None
    groups: bool = False
    brute: bool = True
    extra: str = Field(default="", max_length=5000)


class CreateProblemIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    problem_type: Literal["regular", "interactive", "output_only"] = "regular"
    model: str | None = None
    idea: str | None = Field(default=None, max_length=20000)
    plan: dict | None = None
    groups: bool = False


class GroupsIn(BaseModel):
    plan: dict | None = None
    request: str | None = Field(default=None, max_length=10000)


class PlanIn(BaseModel):
    plan: dict


class EventsSeenIn(BaseModel):
    up_to: int


class SolutionDraftIn(BaseModel):
    tag: str = "OK"
    name: str = Field(default="solution.cpp", max_length=64)
    instruction: str | None = Field(default=None, max_length=5000)


class StatementIn(BaseModel):
    name: str = ""
    legend: str = ""
    input: str = ""
    output: str = ""
    notes: str | None = None
    scoring: str | None = None
    time_limit: int | None = None
    memory_limit: int | None = None
    input_file: str = "stdin"
    output_file: str = "stdout"
    # [[input, output], ...]
    examples: list[list[str]] = Field(default_factory=list, max_length=10)


class CheckerValidatorIn(BaseModel):
    statement: StatementIn
    model: str | None = None


# --------------------------------------------------------------------------- out
def message_out(m: Message) -> dict:
    meta = m.meta or {}
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "timestamp": m.created_at.isoformat() if m.created_at else None,
        "meta": meta,
        "is_error": bool(meta.get("is_error")),
        "updated_files": list(meta.get("changed") or []),
    }


def event_out(e: Event) -> dict:
    return {
        "id": e.id,
        "source": e.source,
        "title": e.title,
        "changes": e.changes or [],
        "seen": e.seen,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def run_out(r: Run | None) -> dict | None:
    if r is None:
        return None
    return {
        "id": r.id,
        "kind": r.kind,
        "status": r.status,
        "step": r.step,
        "progress_done": r.progress_done,
        "progress_total": r.progress_total,
        "error": r.error,
        "result": r.result,
        "parent_run_id": r.parent_run_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }


def build_out(b: Build | None) -> dict | None:
    if b is None:
        return None
    return {
        "id": b.id,
        "run_id": b.run_id,
        "attempt": b.attempt,
        "package_id": b.package_id,
        "state": b.state,
        "comment": b.comment,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }


def session_out(s: AuthoringSession) -> dict:
    settings = s.settings or {}
    return {
        "session_id": s.id,
        "polygon_id": s.polygon_id,
        "problem_type": s.problem_type,
        "model": s.model,
        "auto_build": settings.get("auto_build", True),
        "groups_plan": settings.get("groups_plan"),
        "last_synced_at": s.last_synced_at.isoformat() if s.last_synced_at else None,
        "sync_error": s.sync_error,
    }
