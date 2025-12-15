from sqlalchemy import Column, Integer
from sqlalchemy.orm import relationship

from models.base import Base


class PairOfBannedSubmissions(Base):
    __tablename__ = "pairs_of_banned_submissions"

    id = Column(Integer, primary_key=True)

    percentage = Column(Integer, nullable=False)

    first_submission = relationship(
        "Submission", back_populates="pairs_of_banned_submissions"
    )
    second_submission = relationship(
        "Submission", back_populates="pairs_of_banned_submissions"
    )
