from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.contest.contest import Contest
    from models.plagiarism.pair_of_banned_submissions import \
        PairOfBannedSubmissions


class PlagiarismReport(Base):
    __tablename__ = "plagiarism_reports"

    id: Mapped[int] = mapped_column(primary_key=True)

    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id"))

    status: Mapped[str] = mapped_column(
        default="processing"
    )  # "processing", "completed", "failed"
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    threshold: Mapped[float] = mapped_column()
    only_ok: Mapped[bool] = mapped_column()

    contest: Mapped["Contest"] = relationship(back_populates="plagiarism_reports")

    pairs: Mapped[list["PairOfBannedSubmissions"]] = relationship(
        back_populates="report", cascade="all, delete-orphan", lazy="selectin"
    )
