import enum
from datetime import datetime

from sqlalchemy import ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from models import Base


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
    technical_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    progress: Mapped[dict] = mapped_column(JSON, default=lambda: {"status": "idle"}, nullable=True)

    stage: Mapped[str] = mapped_column(
        default=PipelineStage.STATEMENT,
        nullable=False
    )

    polygon_problem_id: Mapped[int] = mapped_column(nullable=True)
    package_id: Mapped[int] = mapped_column(nullable=True)
    upload_errors: Mapped[dict] = mapped_column(JSON, nullable=True)
    ai_fix_attempts: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column()
