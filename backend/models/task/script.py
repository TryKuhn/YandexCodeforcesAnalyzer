from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.task.problem import PolygonProblem


class PolygonScript(Base):
    """A generation script (per testset) attached to a Polygon problem."""
    __tablename__ = "polygon_scripts"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("polygon_problems.id", ondelete="CASCADE"), index=True
    )

    testset: Mapped[str] = mapped_column(String(64), default="tests")
    content: Mapped[str] = mapped_column(Text)

    uploaded: Mapped[bool] = mapped_column(default=False)

    problem: Mapped["PolygonProblem"] = relationship(back_populates="scripts")

    __table_args__ = (
        UniqueConstraint("problem_id", "testset", name="uq_polygon_scripts_problem_testset"),
    )
