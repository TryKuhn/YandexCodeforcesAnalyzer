from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.task.statement import PolygonStatement
    from models.task.checker import PolygonChecker
    from models.task.validator import PolygonValidator
    from models.task.solution import PolygonSolution
    from models.task.test import PolygonTest
    from models.task.test_group import PolygonTestGroup
    from models.task.generator import PolygonGenerator
    from models.task.script import PolygonScript


class PolygonProblem(Base):
    """Cached representation of a Polygon problem for the current user.

    Fetched lazily: the list is populated from problems.list and individual
    problem details (input/output files, limits, etc.) are loaded on demand
    when the user opens a problem. time_limit is in milliseconds and
    memory_limit is in MB.
    """
    __tablename__ = "polygon_problems"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    polygon_id: Mapped[int] = mapped_column(index=True)
    owner: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(512))

    deleted: Mapped[bool] = mapped_column(default=False)
    favourite: Mapped[bool] = mapped_column(default=False)
    access_type: Mapped[str] = mapped_column(String(16), nullable=True)
    revision: Mapped[int] = mapped_column(nullable=True)
    working_copy_revision: Mapped[int] = mapped_column(nullable=True)
    latest_package: Mapped[int] = mapped_column(nullable=True)
    modified: Mapped[bool] = mapped_column(default=False)

    input_file: Mapped[str] = mapped_column(String(255), nullable=True)
    output_file: Mapped[str] = mapped_column(String(255), nullable=True)
    interactive: Mapped[bool] = mapped_column(default=False)
    well_formed: Mapped[bool] = mapped_column(default=False)
    time_limit: Mapped[int] = mapped_column(nullable=True)
    memory_limit: Mapped[int] = mapped_column(nullable=True)

    list_fetched_at: Mapped[datetime] = mapped_column(nullable=True)
    info_fetched_at: Mapped[datetime] = mapped_column(nullable=True)

    statements: Mapped[List["PolygonStatement"]] = relationship(
        back_populates="problem", cascade="all, delete-orphan"
    )
    checker: Mapped[Optional["PolygonChecker"]] = relationship(
        back_populates="problem", cascade="all, delete-orphan", uselist=False
    )
    validator: Mapped[Optional["PolygonValidator"]] = relationship(
        back_populates="problem", cascade="all, delete-orphan", uselist=False
    )
    solutions: Mapped[List["PolygonSolution"]] = relationship(
        back_populates="problem", cascade="all, delete-orphan"
    )
    tests: Mapped[List["PolygonTest"]] = relationship(
        back_populates="problem", cascade="all, delete-orphan"
    )
    test_groups: Mapped[List["PolygonTestGroup"]] = relationship(
        back_populates="problem", cascade="all, delete-orphan"
    )
    generators: Mapped[List["PolygonGenerator"]] = relationship(
        back_populates="problem", cascade="all, delete-orphan"
    )
    scripts: Mapped[List["PolygonScript"]] = relationship(
        back_populates="problem", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "polygon_id", name="uq_polygon_problems_user_polygon"),
    )
