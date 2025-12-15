from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from models.base import Base


class Contest(Base):
    __tablename__ = "contests"

    id = Column(Integer, primary_key=True)

    name = Column(String(256), nullable=False)
    type = Column(String(5), nullable=False)

    start_time = Column(DateTime, nullable=True)
    finish_time = Column(DateTime, nullable=True)

    participants_of_contest = relationship(
        "ContestParticipant", back_populates="contests"
    )
    tasks = relationship("Task", back_populates="contests")
    pairs_of_banned_submissions = relationship(
        "PairOfBannedSubmission", back_populates="contests"
    )
