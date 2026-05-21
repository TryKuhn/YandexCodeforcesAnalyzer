import enum
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class PipelineStage(str, enum.Enum):
    STATEMENT = "statement"
    FILES_REVIEW = "files_review"
    UPLOADING = "uploading"
    FIXING_ERRORS = "fixing_errors"
    BUILDING_PACKAGE = "building_package"
    DONE = "done"
    FAILED = "failed"


class AISession(Base):
    __tablename__ = "ai_sessions"
    id: Mapped[str] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    model: Mapped[str] = mapped_column()
    system_prompt: Mapped[str] = mapped_column(Text)
    history: Mapped[list] = mapped_column(JSON, default=list)
    statement: Mapped[dict] = mapped_column(JSON, nullable=True)
    progress: Mapped[dict] = mapped_column(
        JSON, default=lambda: {"status": "idle"}, nullable=True
    )

    stage: Mapped[str] = mapped_column(default=PipelineStage.STATEMENT, nullable=False)

    polygon_problem_id: Mapped[int] = mapped_column(nullable=True)
    package_id: Mapped[int] = mapped_column(nullable=True)
    upload_errors: Mapped[dict] = mapped_column(JSON, nullable=True)
    ai_fix_attempts: Mapped[dict] = mapped_column(JSON, default=dict)

    # Problem settings: {input_file, output_file, interactive, time_limit, memory_limit,
    #                    tags: list[str], enable_groups, enable_points}
    problem_settings: Mapped[dict] = mapped_column(JSON, nullable=True)
    # Custom solution metadata: {file_type -> {tag: str, name: str}}
    solution_meta: Mapped[dict] = mapped_column(JSON, nullable=True)
    # Sample/example tests stored in session: [{index, input, output}]
    examples: Mapped[list] = mapped_column(JSON, nullable=True)

    # Human-readable chat log for display in the right panel.
    # Each entry: {id, role, content, timestamp, context?, action?, updated_files?}
    chat_log: Mapped[list] = mapped_column(JSON, default=list, nullable=True)

    created_at: Mapped[datetime] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column()
