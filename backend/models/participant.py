from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from backend.models.base import Base

class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True)

    user_name = Column(String(50), nullable=False)
    user_login = Column(String(50), nullable=False)

    rating = Column(String(50), nullable=False)

    participant_of_contests = relationship("ContestParticipant", back_populates="participants")