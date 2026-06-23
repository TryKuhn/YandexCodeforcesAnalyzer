from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.task.problem import PolygonProblem


class PolygonStatement(Base):
    """A per-language statement (legend, input, output, etc.) for a problem.

    lang holds a Polygon language name such as "russian" or "english".
    """
    __tablename__ = "polygon_statements"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("polygon_problems.id", ondelete="CASCADE"), index=True
    )

    lang: Mapped[str] = mapped_column(String(16))
    encoding: Mapped[str] = mapped_column(String(32), default="utf-8")

    name: Mapped[str] = mapped_column(String(512), nullable=True)
    legend: Mapped[str] = mapped_column(Text, nullable=True)
    input: Mapped[str] = mapped_column(Text, nullable=True)
    output: Mapped[str] = mapped_column(Text, nullable=True)
    scoring: Mapped[str] = mapped_column(Text, nullable=True)
    interaction: Mapped[str] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    tutorial: Mapped[str] = mapped_column(Text, nullable=True)

    uploaded: Mapped[bool] = mapped_column(default=False)

    problem: Mapped["PolygonProblem"] = relationship(back_populates="statements")

    __table_args__ = (
        UniqueConstraint("problem_id", "lang", name="uq_polygon_statements_problem_lang"),
    )
