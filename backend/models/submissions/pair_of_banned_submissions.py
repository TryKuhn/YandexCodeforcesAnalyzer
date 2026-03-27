from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, mapped_column, Mapped

from models.base import Base

if TYPE_CHECKING:
    from models.contest.contest import Contest
    from models.submissions.submission import Submission

class PairOfBannedSubmissions(Base):
    __tablename__ = 'pairs_of_banned_submissions'

    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey('contests.id'))

    first_submission_id: Mapped[int] = mapped_column(ForeignKey('submissions.id'))
    second_submission_id: Mapped[int] = mapped_column(ForeignKey('submissions.id'))

    percentage: Mapped[float] = mapped_column()

    contest: Mapped["Contest"] = relationship(back_populates='pairs_of_banned_submissions')

    submissions: Mapped["Submission"] = relationship(back_populates='pair_of_banned_submissions')
