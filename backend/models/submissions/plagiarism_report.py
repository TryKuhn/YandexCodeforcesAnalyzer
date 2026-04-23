from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class PlagiarismReport(Base):
    __tablename__ = 'plagiarism_reports'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey('contests.id'))

    status: Mapped[str] = mapped_column(String(32), default='processing')
    threshold: Mapped[float] = mapped_column(default=0.8)
    only_ok: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    pairs: Mapped[list["PairOfBannedSubmissions"]] = relationship(
        back_populates='report',
        cascade='all, delete-orphan'
    )