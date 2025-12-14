from sqlalchemy import Column, String, Integer

from backend.models.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)

    task_short_name = Column(String(20), nullable=False)
    task_name = Column(String(100), nullable=False)

    max_score = Column(Integer, nullable=False)
