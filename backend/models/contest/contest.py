from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import relationship, mapped_column, Mapped

from models.base import Base

if TYPE_CHECKING:
    from models.user.user import User
    from models.contest.contest_participant import ContestParticipant
    from models.contest.task import Task
    from models.submissions.pair_of_banned_submissions import PairOfBannedSubmissions

class Contest(Base):
    __tablename__ = 'contests'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_login: Mapped[str] = mapped_column(String(50), ForeignKey('users.login'))

    name: Mapped[str] = mapped_column(String(256))
    type: Mapped[str] = mapped_column(String(5))

    start_time: Mapped[datetime | None] = mapped_column()
    finish_time: Mapped[datetime | None] = mapped_column()

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
