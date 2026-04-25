from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import relationship, mapped_column, Mapped

from models.base import Base

if TYPE_CHECKING:
    from models.participant.participant import Participant
    from models.contest.contest import Contest
    from models.contest.task_result import TaskResult

class ContestParticipant(Base):
    __tablename__ = 'contest_participants'

    id: Mapped[int] = mapped_column(primary_key=True)

    contest_id: Mapped[int] = mapped_column(ForeignKey('contests.id'))
    participant_id: Mapped[int] = mapped_column(ForeignKey('participants.id'))

    login: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))

    score: Mapped[float | None] = mapped_column()

    contest: Mapped['Contest'] = relationship(back_populates='contest_participants')

    participant: Mapped['Participant'] = relationship(back_populates='contest_participants')

    tasks_results: Mapped[list["TaskResult"]] = relationship(
        back_populates='contest_participant',
        cascade='all, delete-orphan',
    )
