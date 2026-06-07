from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.task.problem import PolygonProblem


class PolygonTestGroup(Base):
    """A test group within a testset.

    pointsPolicy: COMPLETE_GROUP | EACH_TEST
    feedbackPolicy: NONE | POINTS | ICPC | COMPLETE
    """
    __tablename__ = "polygon_test_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("polygon_problems.id", ondelete="CASCADE"), index=True
    )

    testset: Mapped[str] = mapped_column(String(64), default="tests")
    name: Mapped[str] = mapped_column(String(128))
    points_policy: Mapped[str] = mapped_column(String(32), nullable=True)
    feedback_policy: Mapped[str] = mapped_column(String(32), nullable=True)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)

    problem: Mapped["PolygonProblem"] = relationship(back_populates="test_groups")

    __table_args__ = (
        UniqueConstraint(
            "problem_id", "testset", "name", name="uq_polygon_test_groups_problem_testset_name"
        ),
    )
