from sqlalchemy import Column, DateTime, Integer, String

from models.base import Base


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True)

    send_time = Column(DateTime, nullable=False)

    language = Column(String(50), nullable=False)

    score = Column(Integer, nullable=True)
    verdict = Column(String(50), nullable=False)
    run_time = Column(Integer, nullable=False)

    source = Column(String(100000), nullable=False)
