from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

from models import Base


class PlagiarismReport(Base):
    __tablename__ = 'plagiarism_reports'

    id: Mapped[int] = mapped_column(primary_key=True)

    contest_id: Mapped[int] = mapped_column(ForeignKey('contests.id'))

    status: Mapped[str] = mapped_column(default="processing")  # "processing", "completed", "failed"
    created_at: Mapped[datetime] = mapped_column(default=datetime.now().replace(tzinfo=None))
    threshold: Mapped[float] = mapped_column()

    contest = relationship(back_populates="plagiarism_reports")