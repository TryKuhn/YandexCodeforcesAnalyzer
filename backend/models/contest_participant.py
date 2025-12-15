from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from models.base import Base


class ContestParticipant(Base):
    __tablename__ = "contest_participants"

    id = Column(Integer, primary_key=True)

    login = Column(String(50), nullable=False)
    name = Column(String(50), nullable=True)

    score = Column(Integer, nullable=False)

    tasks_result = relationship("TaskResult", back_populates="contest_participants")
