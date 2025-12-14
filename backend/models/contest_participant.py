from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from backend.models.base import Base


class ContestParticipant(Base):
    __tablename__ = "contest_participants"

    id = Column(Integer, primary_key=True)

    user_login = Column(String(50), nullable=False)
    user_name = Column(String(50), nullable=False)

    total_score = Column(Integer, nullable=False)

    task_result = relationship("TaskResult", back_populates="contest_participants")
