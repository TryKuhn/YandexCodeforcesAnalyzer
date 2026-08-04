"""A contestant's submission and its judging outcome."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, utcnow

if TYPE_CHECKING:
    from models.judge.run import JudgeRun


class JudgeSubmission(Base):
    __tablename__ = "judge_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("judge_problems.id", ondelete="CASCADE")
    )
    # flat id: participant accounts are another domain
    user_id: Mapped[int | None] = mapped_column()

    # language registry id (cpp / python)
    language: Mapped[str] = mapped_column(String(16))
    source_sha: Mapped[str] = mapped_column(String(64))

    # queued -> running -> judged; failed = judge infra broke, not the solution
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    verdict: Mapped[str | None] = mapped_column(String(16))
    score: Mapped[float | None] = mapped_column()

    max_time_ms: Mapped[int | None] = mapped_column()
    max_memory_kb: Mapped[int | None] = mapped_column()
    first_failed_test: Mapped[int | None] = mapped_column()
    compile_log_sha: Mapped[str | None] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    judged_at: Mapped[datetime | None] = mapped_column()

    runs: Mapped[list["JudgeRun"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="JudgeRun.test_index",
        lazy="selectin",
    )
