from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.task.session import TaskSession


class TaskGeneratedFile(Base):
    """An AI-generated file for a TaskSession (validator, checker, solution, etc.).

    Replaces AIGeneratedFile and reuses the 'ai_generated_files' table so no
    data migration is required when upgrading from the old model.
    """
    __tablename__ = "ai_generated_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("ai_sessions.id", ondelete="CASCADE"), index=True
    )

    filename: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    file_type: Mapped[str] = mapped_column(String(64))

    uploaded: Mapped[bool] = mapped_column(default=False)

    session: Mapped["TaskSession"] = relationship(back_populates="generated_files")
