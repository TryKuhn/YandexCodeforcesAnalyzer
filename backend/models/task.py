from sqlalchemy import Column, Integer, String

from models.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)

    short_name = Column(String(20), nullable=True)
    full_name = Column(String(100), nullable=False)

    max_score = Column(Integer, nullable=True)
