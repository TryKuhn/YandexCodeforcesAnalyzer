"""In-memory store for archive-import jobs.

A single uvicorn process makes a plain dict sufficient: jobs live until the
process restarts, and the oldest are evicted once ``MAX_JOBS`` is exceeded.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

MAX_JOBS = 30

PROBLEM_STAGES = [
    "wait",
    "create",
    "statement",
    "files",
    "tests",
    "groups",
    "commit",
    "build",
    "done",
    "error",
]
"""Per-problem upload stages, in execution order.

``wait`` (queued) -> ``create`` (create/find problem) -> ``statement``
(limits + statement + images) -> ``files`` (solutions + checker/validator) ->
``tests`` -> ``groups`` (groups/points) -> ``commit`` -> ``build`` (build
package), ending in the terminal ``done`` or ``error`` states.
"""


@dataclass
class ProblemStatus:
    """Live progress of importing one problem.

    ``name`` is the archive letter (A, B, ...) and ``polygon_name`` the target
    Polygon problem name; ``checker``/``validator`` hold the name or type of the
    file installed for each.
    """

    name: str
    polygon_name: str
    polygon_id: int | None = None
    stage: str = "wait"
    error: str | None = None
    solutions_total: int = 0
    solutions_done: int = 0
    tests_total: int = 0
    tests_done: int = 0
    groups_total: int = 0
    images_total: int = 0
    checker: str | None = None
    validator: str | None = None
    log: list[str] = field(default_factory=list)

    def note(self, msg: str) -> None:
        """Append a human-readable progress message to the log."""
        self.log.append(msg)

    def to_dict(self) -> dict:
        """Serialize for the status endpoint, keeping only the last 20 log lines."""
        return {
            "name": self.name,
            "polygon_name": self.polygon_name,
            "polygon_id": self.polygon_id,
            "stage": self.stage,
            "error": self.error,
            "solutions_total": self.solutions_total,
            "solutions_done": self.solutions_done,
            "tests_total": self.tests_total,
            "tests_done": self.tests_done,
            "groups_total": self.groups_total,
            "images_total": self.images_total,
            "checker": self.checker,
            "validator": self.validator,
            "log": self.log[-20:],
        }


@dataclass
class ImportJob:
    """A single archive-import job and the per-problem statuses it spawns.

    ``status`` moves through ``parsing | running | done | error``.
    """

    id: str
    user_id: int
    status: str = "parsing"
    error: str | None = None
    archive_name: str = ""
    prefix: str = ""
    problems: list[ProblemStatus] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        """Serialize the job and its problems for the status endpoint."""
        return {
            "job_id": self.id,
            "status": self.status,
            "error": self.error,
            "archive_name": self.archive_name,
            "prefix": self.prefix,
            "created_at": self.created_at.isoformat(),
            "problems": [p.to_dict() for p in self.problems],
        }


JOBS: dict[str, ImportJob] = {}


def create_job(user_id: int, archive_name: str) -> ImportJob:
    """Create and register a new job, evicting the oldest jobs over the limit."""
    if len(JOBS) >= MAX_JOBS:
        for jid in sorted(JOBS, key=lambda j: JOBS[j].created_at)[: len(JOBS) - MAX_JOBS + 1]:
            JOBS.pop(jid, None)
    job = ImportJob(id=uuid.uuid4().hex, user_id=user_id, archive_name=archive_name)
    JOBS[job.id] = job
    return job


def get_job(job_id: str, user_id: int) -> ImportJob | None:
    """Return the job if it exists and belongs to ``user_id``, else ``None``."""
    job = JOBS.get(job_id)
    if job is None or job.user_id != user_id:
        return None
    return job
