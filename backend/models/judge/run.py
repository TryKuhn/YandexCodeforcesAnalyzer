"""Result of one submission on one test."""
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.judge.submission import JudgeSubmission


class JudgeRun(Base):
    __tablename__ = "judge_runs"
    __table_args__ = (UniqueConstraint("submission_id", "test_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("judge_submissions.id", ondelete="CASCADE")
    )
    # plain index, not an FK: tests may be regenerated, history must survive
    test_index: Mapped[int] = mapped_column()

    verdict: Mapped[str] = mapped_column(String(16))
    time_ms: Mapped[int] = mapped_column(default=0)
    memory_kb: Mapped[int] = mapped_column(default=0)
    points: Mapped[float | None] = mapped_column()
    # short checker output shown to the jury
    checker_comment: Mapped[str | None] = mapped_column(Text)

    submission: Mapped["JudgeSubmission"] = relationship(back_populates="runs")
