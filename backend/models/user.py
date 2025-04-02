from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from base import Base


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)

    login = Column(String(50), unique=True, nullable=False)
    password = Column(String(120), nullable=False)

    codeforces_api_key = Column(String(100))
    codeforces_api_secret = Column(String(100))

    yandex_access_token = Column(String(255))

    telegram_id = Column(String(50))

    competition_results = relationship('CompetitionResult', back_populates='user', cascade='all, delete-orphan')
    participant_results = relationship('ParticipantAttempt', back_populates='user', cascade='all, delete-orphan')
