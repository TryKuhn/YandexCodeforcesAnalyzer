from sqlalchemy import Column, Integer, JSON, ForeignKey
from sqlalchemy.orm import relationship

from models.base import Base


class ContestResult(Base):
    __tablename__ = 'contest_results'

    id = Column(Integer, primary_key=True)

    result_data = Column(JSON)

    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', back_populates='contest_results')
