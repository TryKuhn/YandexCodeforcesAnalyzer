from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.contest.contest_participant import ContestParticipant
    from models.user.user import User


class Participant(Base):
    """A competitor tracked across a user's contests."""
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    login: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))

    rating: Mapped[float | None] = mapped_column()

    user: Mapped["User"] = relationship(back_populates="participants")

    contest_participants: Mapped[list["ContestParticipant"]] = relationship(
        back_populates="participant"
    )
