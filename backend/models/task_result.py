from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from models.base import Base


class TaskResult(Base):
    __tablename__ = "task_results"

    id = Column(Integer, primary_key=True)

    score = Column(Integer, nullable=True)
    tries_count = Column(Integer, nullable=True)
    verdict = Column(String(50), nullable=False)

    last_success_time = Column(DateTime, nullable=True)

    banned = Column(Boolean, nullable=False)

    submissions = relationship("Submission", back_populates="task_results")
    task = relationship("Task", back_populates="task_results")
