from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.task.problem import PolygonProblem


class PolygonChecker(Base):
    __tablename__ = "polygon_checkers"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("polygon_problems.id", ondelete="CASCADE"), unique=True, index=True
    )

    name: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(64), nullable=True)  # e.g. "cpp.g++17"

    uploaded: Mapped[bool] = mapped_column(default=False)

    problem: Mapped["PolygonProblem"] = relationship(back_populates="checker")
