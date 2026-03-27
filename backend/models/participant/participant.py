from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import relationship, Mapped, mapped_column

from models.base import Base

if TYPE_CHECKING:
    from models.contest.contest_participant import ContestParticipant
    from models.user.user import User


class Participant(Base):
    __tablename__ = 'participants'

    id: Mapped[int] = mapped_column(primary_key=True)

    login: Mapped[str] = mapped_column(String(50))
    name: Mapped[str | None] = mapped_column(String(50))

    rating: Mapped[float] = mapped_column()

    user: Mapped["User"] = relationship(back_populates='participants')

    participant_of_contests: Mapped[list["ContestParticipant"]] = relationship(back_populates='participant')
