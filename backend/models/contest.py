from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import relationship, mapped_column, Mapped

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.user import User
    from backend.models.contest_participant import ContestParticipant
    from backend.models.task import Task
    from backend.models.pair_of_banned_submissions import PairOfBannedSubmissions

class Contest(Base):
    __tablename__ = 'contests'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_login: Mapped[str] = mapped_column(String(50), ForeignKey('users.login'))

    name: Mapped[str] = mapped_column(String(256))
    type: Mapped[str] = mapped_column(String(5))

    start_time: Mapped[DateTime | None] = mapped_column()
    finish_time: Mapped[DateTime | None] = mapped_column()

    user: Mapped["User"] = relationship(back_populates='contests')

    contest_participants: Mapped[list["ContestParticipant"]] = relationship(
        back_populates='contest',
        cascade='all, delete-orphan'
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates='contest',
        cascade='all, delete-orphan'
    )
    pairs_of_banned_submissions: Mapped[list["PairOfBannedSubmissions"]] = relationship(
        back_populates='contest',
        cascade='all, delete-orphan'
    )
