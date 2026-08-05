"""A problem as our judge sees it; heavy artifacts are blob hashes, not inline text."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, utcnow

if TYPE_CHECKING:
    from models.judge.test import JudgeTest


class JudgeProblem(Base):
    __tablename__ = "judge_problems"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))

    time_limit_ms: Mapped[int] = mapped_column(default=1000)
    memory_limit_mb: Mapped[int] = mapped_column(default=256)

    # testlib sources by blob hash; null while the problem is still a draft
    checker_sha: Mapped[str | None] = mapped_column(String(64))
    validator_sha: Mapped[str | None] = mapped_column(String(64))
    interactor_sha: Mapped[str | None] = mapped_column(String(64))

    # flat id: judge tables must not grow FKs into other domains
    user_id: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    # selectin: test lists are small and always wanted together with the problem
    tests: Mapped[list["JudgeTest"]] = relationship(
        back_populates="problem",
        cascade="all, delete-orphan",
        order_by="JudgeTest.index",
        lazy="selectin",
    )
