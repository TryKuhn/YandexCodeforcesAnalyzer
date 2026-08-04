"""One test of a problem; input and answer are blob hashes, so identical tests dedup for free."""
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.judge.problem import JudgeProblem


class JudgeTest(Base):
    __tablename__ = "judge_tests"
    __table_args__ = (UniqueConstraint("problem_id", "index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("judge_problems.id", ondelete="CASCADE")
    )
    # 1-based position within the problem
    index: Mapped[int] = mapped_column()

    input_sha: Mapped[str] = mapped_column(String(64))
    # computed by running the main solution; null until then
    answer_sha: Mapped[str | None] = mapped_column(String(64))

    # IOI-style scoring; null for plain ICPC tests
    group_name: Mapped[str | None] = mapped_column(String(32))
    points: Mapped[int | None] = mapped_column()

    problem: Mapped["JudgeProblem"] = relationship(back_populates="tests")
