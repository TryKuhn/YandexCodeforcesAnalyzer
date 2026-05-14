from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.contest.task_result import TaskResult
    from models.plagiarism.pair_of_banned_submissions import \
        PairOfBannedSubmissions


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(primary_key=True)

    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id"))
    task_result_id: Mapped[int] = mapped_column(ForeignKey("task_results.id"))

    participant_login: Mapped[str] = mapped_column(String(255))
    task_name: Mapped[str] = mapped_column(String(500))

    send_time: Mapped[datetime] = mapped_column()

    language: Mapped[str] = mapped_column(String(50))

    score: Mapped[float | None] = mapped_column()
    verdict: Mapped[str] = mapped_column(String(50))

    run_time: Mapped[timedelta] = mapped_column()
    memory_bytes: Mapped[int] = mapped_column()

    banned: Mapped[bool] = mapped_column(default=False)

    source: Mapped[str | None] = mapped_column()

    task_result: Mapped["TaskResult"] = relationship(back_populates="submissions")

    banned_as_first: Mapped[list["PairOfBannedSubmissions"]] = relationship(
        primaryjoin="Submission.id==PairOfBannedSubmissions.first_submission_id",
        back_populates="first_submission",
    )
    banned_as_second: Mapped[list["PairOfBannedSubmissions"]] = relationship(
        primaryjoin="Submission.id==PairOfBannedSubmissions.second_submission_id",
        back_populates="second_submission",
    )
