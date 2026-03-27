from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import relationship, Mapped, mapped_column

from models.base import Base

if TYPE_CHECKING:
    from models.contest.contest import Contest
    from models.contest.task_result import TaskResult


class Task(Base):
    __tablename__ = 'tasks'

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey('contests.id'))

    short_name: Mapped[str | None] = mapped_column(String(20))
    full_name: Mapped[str] = mapped_column(String(100))

    max_score: Mapped[int | None] = mapped_column()

    contest: Mapped["Contest"] = relationship(back_populates='tasks')
    task_results: Mapped[list["TaskResult"]] = relationship(back_populates='task')

