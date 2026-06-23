import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.task.generated_file import TaskGeneratedFile
    from models.task.problem import PolygonProblem


class PipelineStage(str, enum.Enum):
    """Stages of the AI problem-creation pipeline, from statement to done/failed."""
    STATEMENT = "statement"
    FILES_REVIEW = "files_review"
    UPLOADING = "uploading"
    FIXING_ERRORS = "fixing_errors"
    BUILDING_PACKAGE = "building_package"
    DONE = "done"
    FAILED = "failed"


class ProblemType(str, enum.Enum):
    """The kind of problem being authored, which drives generation branching.

    REGULAR      — statement, tests, generator, validator, checker, solutions.
    INTERACTIVE  — REGULAR + interactor + an "interaction" statement section.
    OUTPUT_ONLY  — participant submits an answer archive; a checker-scorer
                   grades it against the jury answer and awards partial points.
    """
    REGULAR = "regular"
    INTERACTIVE = "interactive"
    OUTPUT_ONLY = "output_only"


class TaskSession(Base):
    """AI-assisted problem-creation session.

    Replaces the old AISession model and reuses the 'ai_sessions' table so no
    data migration is required when upgrading from the old model.

    Key fields:
    - polygon_problem_id: Polygon API problem ID (set after problem.create).
    - cached_polygon_problem_id: FK to the local PolygonProblem cache row.
    - statement: {name, legend, input, output, notes, tutorial}.
    - problem_settings: {input_file, output_file, interactive, time_limit,
      memory_limit, tags: list[str], enable_groups, enable_points}.
    - upload_errors: {file_key -> {file_name, error, needs_manual_fix}}.
    - solution_meta: {file_type -> {tag: str, name: str}}.
    - examples: [{index, input, output}].
    - chat_log: human-readable log of [{id, role, content, timestamp, ...}].
    """
    __tablename__ = "ai_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    model: Mapped[str] = mapped_column(String(128))
    system_prompt: Mapped[str] = mapped_column(Text)
    history: Mapped[list] = mapped_column(JSON, default=list)

    problem_type: Mapped[str] = mapped_column(
        String(16), default=ProblemType.REGULAR, nullable=False
    )

    stage: Mapped[str] = mapped_column(
        String(32), default=PipelineStage.STATEMENT, nullable=False
    )
    progress: Mapped[Optional[dict]] = mapped_column(
        JSON, default=lambda: {"status": "idle"}, nullable=True
    )

    statement: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    problem_settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    polygon_problem_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    package_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    cached_polygon_problem_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("polygon_problems.id"), nullable=True
    )
    cached_problem: Mapped[Optional["PolygonProblem"]] = relationship(
        "PolygonProblem", foreign_keys=[cached_polygon_problem_id]
    )

    upload_errors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ai_fix_attempts: Mapped[dict] = mapped_column(JSON, default=dict)

    solution_meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    examples: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    chat_log: Mapped[list] = mapped_column(JSON, default=list, nullable=True)

    created_at: Mapped[datetime] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column()

    generated_files: Mapped[List["TaskGeneratedFile"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
