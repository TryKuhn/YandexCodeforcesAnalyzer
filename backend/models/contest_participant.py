from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import relationship, mapped_column, Mapped

from backend.models.base import Base

if TYPE_CHECKING:
    from backend.models.contest import Contest
    from backend.models.task_result import TaskResult

class ContestParticipant(Base):
    __tablename__ = 'contest_participants'

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey('contests.id'))

    login: Mapped[str] = mapped_column(String(50))
    name: Mapped[str | None] = mapped_column(String(50))

    score: Mapped[int] = mapped_column()

    contest: Mapped["Contest"] = relationship(back_populates='contest_participants')

    tasks_results: Mapped[list["TaskResult"]] = relationship(back_populates='contest_participant')
