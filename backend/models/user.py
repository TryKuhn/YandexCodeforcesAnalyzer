from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from backend.models.base import Base


class User(Base):
    __tablename__ = "users"

    login = Column(String(50), primary_key=True, nullable=False)
    password = Column(String(120), nullable=False)

    codeforces_api_key = Column(String(100))
    codeforces_api_secret = Column(String(100))

    yandex_access_token = Column(String(255))

    contest = relationship("Contest", back_populates="users")
    contest_results = relationship("ContestResult", back_populates="user")
    participant_attempts = relationship("ParticipantAttempt", back_populates="user")
    participants = relationship("Participant", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user")
