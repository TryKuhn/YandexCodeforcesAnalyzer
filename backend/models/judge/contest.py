"""Contests of our own judge and who takes part in them."""
import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, utcnow

if TYPE_CHECKING:
    from models.judge.problem import JudgeProblem


class ScoringKind(str, enum.Enum):
    # solved count first, penalty time breaks ties
    ICPC = "icpc"
    # sum of the best score per problem
    IOI = "ioi"


class JudgeContest(Base):
    __tablename__ = "judge_contests"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    scoring: Mapped[str] = mapped_column(String(8), default=ScoringKind.ICPC.value)

    starts_at: Mapped[datetime] = mapped_column(default=utcnow)
    ends_at: Mapped[datetime | None] = mapped_column()
    # after this many minutes the public board stops updating (ICPC freeze)
    freeze_minutes: Mapped[int | None] = mapped_column()

    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    problems: Mapped[list["JudgeContestProblem"]] = relationship(
        back_populates="contest",
        cascade="all, delete-orphan",
        order_by="JudgeContestProblem.position",
        lazy="selectin",
    )


class JudgeContestProblem(Base):
    """A problem's slot in a contest: its letter and, for IOI, its weight."""

    __tablename__ = "judge_contest_problems"
    __table_args__ = (
        UniqueConstraint("contest_id", "position"),
        UniqueConstraint("contest_id", "problem_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(
        ForeignKey("judge_contests.id", ondelete="CASCADE")
    )
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("judge_problems.id", ondelete="CASCADE")
    )
    # 0 -> A, 1 -> B, ...
    position: Mapped[int] = mapped_column()
    max_points: Mapped[float] = mapped_column(default=100.0)

    contest: Mapped["JudgeContest"] = relationship(back_populates="problems")
    problem: Mapped["JudgeProblem"] = relationship(lazy="selectin")

    @property
    def letter(self) -> str:
        return chr(ord("A") + self.position)


class JudgeContestParticipant(Base):
    __tablename__ = "judge_contest_participants"
    __table_args__ = (UniqueConstraint("contest_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(
        ForeignKey("judge_contests.id", ondelete="CASCADE")
    )
    # flat id: accounts belong to another domain
    user_id: Mapped[int] = mapped_column()
    display_name: Mapped[str] = mapped_column(String(255))
    # out-of-competition entries are shown but not ranked
    is_official: Mapped[bool] = mapped_column(default=True)

    registered_at: Mapped[datetime] = mapped_column(default=utcnow)
