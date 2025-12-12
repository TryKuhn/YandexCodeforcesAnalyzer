from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from models.base import Base


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True)

    user_login = Column(String(50), nullable=False)
    contest_id = Column(Integer, ForeignKey("contests.id"))

    user = relationship("User", back_populates="participants")
    contest = relationship("Contest", back_populates="participants")
