from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, mapped_column, Mapped

from models.base import Base

if TYPE_CHECKING:
    from models.contest.contest import Contest
    from models.submissions.submission import Submission
    from models.plagiarism.plagiarism_report import PlagiarismReport


class PairOfBannedSubmissions(Base):
    __tablename__ = 'pair_of_banned_submissions'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    contest_id: Mapped[int] = mapped_column(ForeignKey('contests.id'))
    report_id: Mapped[int] = mapped_column(ForeignKey('plagiarism_reports.id'))

    first_submission_id: Mapped[str] = mapped_column(ForeignKey('submissions.id'))
    second_submission_id: Mapped[str] = mapped_column(ForeignKey('submissions.id'))

    percentage: Mapped[float] = mapped_column()

    contest: Mapped["Contest"] = relationship(back_populates='pairs_of_banned_submissions')
    report: Mapped["PlagiarismReport"] = relationship(back_populates='pairs')

    first_submission: Mapped["Submission"] = relationship(
        foreign_keys=[first_submission_id],
        back_populates='banned_as_first'
    )
    second_submission: Mapped["Submission"] = relationship(
        foreign_keys=[second_submission_id],
        back_populates='banned_as_second'
    )