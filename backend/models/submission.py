from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import relationship, Mapped, mapped_column

from models.base import Base

if TYPE_CHECKING:
    from models.task_result import TaskResult
    from models.pair_of_banned_submissions import PairOfBannedSubmissions


class Submission(Base):
    __tablename__ = 'submissions'

    id: Mapped[int] = mapped_column(primary_key=True)

    contest_id: Mapped[int] = mapped_column(ForeignKey('contests.id'))
    task_result_id: Mapped[int] = mapped_column(ForeignKey('task_results.id'))

    participant_login: Mapped[str] = mapped_column(String(50))
    task_name: Mapped[str] = mapped_column(String(50))

    send_time: Mapped[datetime] = mapped_column()

    language: Mapped[str] = mapped_column(String(50))

    score: Mapped[int | None] = mapped_column()
    verdict: Mapped[str] = mapped_column(String(50))
    run_time: Mapped[int] = mapped_column()
    banned: Mapped[bool] = mapped_column(default=False)

    source: Mapped[str | None] = mapped_column()

    task_result: Mapped["TaskResult"] = relationship(back_populates='submissions')
    pair_of_banned_submissions: Mapped["PairOfBannedSubmissions"] = relationship(back_populates='submissions')
