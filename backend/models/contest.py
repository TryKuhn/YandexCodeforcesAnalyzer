from sqlalchemy import Column, Integer
from sqlalchemy.orm import relationship

from models.base import Base


class Contest(Base):
    __table__ = "contests"

    id = Column(Integer, primary_key=True)

    contest_result = relationship("ContestResult", back_populates="contest")
    participants = relationship("Participant", back_populates="contest")
