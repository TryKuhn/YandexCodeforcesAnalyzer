from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from backend.models.base import Base

class Contest(Base):
    __tablename__ = "contests"

    id = Column(Integer, primary_key=True)
    contest_name = Column(String(256), nullable=False)

    contest_type = Column(String(5))

    start_time = Column(DateTime, nullable=False)
    finish_time = Column(DateTime, nullable=False)

    participants_of_contest = relationship("ContestParticipant", back_populates="contests")

    tasks = relationship("Task", back_populates="contests")

    pairs_of_banned_submissions = relationship("PairOfBannedSubmission", back_populates="contests")
