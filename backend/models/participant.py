from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from models.base import Base


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True)

    login = Column(String(50), nullable=False)
    name = Column(String(50), nullable=True)

    rating = Column(String(50), nullable=False)

    participant_of_contests = relationship(
        "ContestParticipant", back_populates="participants"
    )
