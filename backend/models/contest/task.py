from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.contest.contest import Contest
    from models.contest.task_result import TaskResult


class Task(Base):
    """A problem (task) belonging to a contest."""
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id"))

    short_name: Mapped[str | None] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(500))

    max_score: Mapped[float | None] = mapped_column()

    task_results: Mapped[list["TaskResult"]] = relationship(back_populates="task")

    contest: Mapped["Contest"] = relationship(back_populates="tasks")
