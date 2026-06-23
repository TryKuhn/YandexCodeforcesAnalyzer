from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.task.problem import PolygonProblem


class PolygonSolution(Base):
    """A solution file attached to a problem.

    tag values: MA (Main), OK, RJ, TL, TO, TM, WA, PE, ML, NR, RE
    """
    __tablename__ = "polygon_solutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("polygon_problems.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(64), nullable=True)
    tag: Mapped[str] = mapped_column(String(8), nullable=True)

    uploaded: Mapped[bool] = mapped_column(default=False)

    problem: Mapped["PolygonProblem"] = relationship(back_populates="solutions")

    __table_args__ = (
        UniqueConstraint("problem_id", "name", name="uq_polygon_solutions_problem_name"),
    )
