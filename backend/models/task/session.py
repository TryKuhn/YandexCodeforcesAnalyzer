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
    STATEMENT = "statement"
    FILES_REVIEW = "files_review"
    UPLOADING = "uploading"
    FIXING_ERRORS = "fixing_errors"
    BUILDING_PACKAGE = "building_package"
    DONE = "done"
    FAILED = "failed"


class TaskSession(Base):
    """AI-assisted problem-creation session.

    Replaces the old AISession model. Uses the same table ('ai_sessions') so
    no data migration is required when upgrading from the old model.

    `polygon_problem_id`         — Polygon API problem ID (set after problem.create).
    `cached_polygon_problem_id`  — FK to our local PolygonProblem cache row.
    """
    __tablename__ = "ai_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    model: Mapped[str] = mapped_column(String(128))
    system_prompt: Mapped[str] = mapped_column(Text)
    history: Mapped[list] = mapped_column(JSON, default=list)

    stage: Mapped[str] = mapped_column(
        String(32), default=PipelineStage.STATEMENT, nullable=False
    )
    progress: Mapped[Optional[dict]] = mapped_column(
        JSON, default=lambda: {"status": "idle"}, nullable=True
    )

    # AI-generated statement: {name, legend, input, output, notes, tutorial}
    statement: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Problem settings: {input_file, output_file, interactive, time_limit, memory_limit,
    #                    tags: list[str], enable_groups, enable_points}
    problem_settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Polygon IDs set after problem.create / package build
    polygon_problem_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    package_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    # FK to our local problem cache (set once the problem exists on Polygon)
    cached_polygon_problem_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("polygon_problems.id"), nullable=True
    )
    cached_problem: Mapped[Optional["PolygonProblem"]] = relationship(
        "PolygonProblem", foreign_keys=[cached_polygon_problem_id]
    )

    # Upload error tracking: {file_key -> {file_name, error, needs_manual_fix}}
    upload_errors: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ai_fix_attempts: Mapped[dict] = mapped_column(JSON, default=dict)

    # Solution metadata: {file_type -> {tag: str, name: str}}
    solution_meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Sample/example tests: [{index, input, output}]
    examples: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Human-readable chat log: [{id, role, content, timestamp, ...}]
    chat_log: Mapped[list] = mapped_column(JSON, default=list, nullable=True)

    created_at: Mapped[datetime] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column()

    generated_files: Mapped[List["TaskGeneratedFile"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
