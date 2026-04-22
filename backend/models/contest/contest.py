from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import relationship, mapped_column, Mapped

from models.base import Base

if TYPE_CHECKING:
    from models.contest.contest_participant import ContestParticipant
    from models.contest.task import Task
    from models.submissions.pair_of_banned_submissions import PairOfBannedSubmissions
    from models.user.user import User

class Contest(Base):
    __tablename__ = 'contests'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))

    platform: Mapped[str] = mapped_column(String(100))
    external_id: Mapped[int] = mapped_column()

    name: Mapped[str] = mapped_column(String(256))
    type: Mapped[str] = mapped_column(String(5))

    unofficial: Mapped[bool] = mapped_column()

    start_time: Mapped[datetime | None] = mapped_column()
    duration: Mapped[timedelta | None] = mapped_column()

    user: Mapped['User'] = relationship(back_populates='contests')

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
