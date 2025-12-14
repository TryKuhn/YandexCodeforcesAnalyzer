from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship

from backend.models.base import Base


class TaskResult(Base):
    __tablename__ = "task_results"

    id = Column(Integer, primary_key=True)

    score = Column(Integer, nullable=True)

    verdict = Column(String(50), nullable=True)

    last_success_time = Column(DateTime, nullable=True)

    banned = Column(Boolean, nullable=True)

    submissions = relationship("Submission", back_populates="task_results")
    task = relationship("Task", back_populates="task_results")

