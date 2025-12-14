from sqlalchemy import Column, Integer
from sqlalchemy.orm import relationship

from backend.models.base import Base

class PairOfBannedSubmissions(Base):
    __tablename__ = "pairs_of_banned_submissions"

    first_submission = relationship("Submission", back_populates="pairs_of_banned_submissions")
    second_submission = relationship("Submission", back_populates="pairs_of_banned_submissions")

    percentage = Column(Integer, nullable=True)

