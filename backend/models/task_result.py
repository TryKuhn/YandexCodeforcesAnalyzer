from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import relationship, Mapped, mapped_column

from models.base import Base

if TYPE_CHECKING:
    from models.contest_participant import ContestParticipant
    from models.task import Task
    from models.submission import Submission

class TaskResult(Base):
    __tablename__ = 'task_results'

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_participant_id: Mapped[int] = mapped_column(ForeignKey('contest_participants.id'))
    task_id: Mapped[int] = mapped_column(ForeignKey('tasks.id'))

    score: Mapped[int | None] = mapped_column()
    tries_count: Mapped[int | None] = mapped_column()
    verdict: Mapped[str] = mapped_column(String(50))

    last_success_time: Mapped[datetime] = mapped_column()

    banned: Mapped[bool] = mapped_column(default=False)

    contest_participant: Mapped["ContestParticipant"] = relationship(back_populates='tasks_results')

    task: Mapped["Task"] = relationship(back_populates='task_results')
    submissions: Mapped["Submission"] = relationship(back_populates='task_result')
