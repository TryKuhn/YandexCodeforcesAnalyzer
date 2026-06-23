from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.user.user import User


class Role(Base):
    """An access role (e.g. User, Admin) assignable to users."""
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(100))

    user: Mapped[list["User"]] = relationship(back_populates="role")
