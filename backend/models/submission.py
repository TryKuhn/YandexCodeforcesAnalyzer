from sqlalchemy import Column, Integer, String, DateTime

from backend.models.base import Base

class Submission(Base):
    __tablename__ = "submission"

    submission_id = Column(Integer, primary_key=True)

    start_time = Column(DateTime, nullable=False)
    finish_time = Column(DateTime, nullable=False)

    score = Column(Integer, nullable=True)

    language = Column(String(50), nullable=False)

    verdict = Column(String(50), nullable=False)

    runtime = Column(Integer, nullable=False)

    sourse = Column(String(100000), nullable=False)

