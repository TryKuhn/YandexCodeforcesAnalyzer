from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.task.problem import PolygonProblem


class PolygonTest(Base):
    """A single test case for a problem.

    testInput is stored as binary (bytes are base64-encoded in the column)
    to handle arbitrary binary content correctly.
    """
    __tablename__ = "polygon_tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("polygon_problems.id", ondelete="CASCADE"), index=True
    )

    testset: Mapped[str] = mapped_column(String(64), default="tests")
    index: Mapped[int] = mapped_column()

    input_b64: Mapped[str] = mapped_column(Text, nullable=True)

    group: Mapped[str] = mapped_column(String(128), nullable=True)
    points: Mapped[float] = mapped_column(nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    use_in_statements: Mapped[bool] = mapped_column(default=False)
    input_for_statements: Mapped[str] = mapped_column(Text, nullable=True)
    output_for_statements: Mapped[str] = mapped_column(Text, nullable=True)

    uploaded: Mapped[bool] = mapped_column(default=False)

    problem: Mapped["PolygonProblem"] = relationship(back_populates="tests")

    __table_args__ = (
        UniqueConstraint(
            "problem_id", "testset", "index", name="uq_polygon_tests_problem_testset_index"
        ),
    )
