from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from backend.models.base import Base


class User(Base):
    __tablename__ = "user"

    login = Column(String(50), primary_key=True, nullable=False)
    password = Column(String(120), nullable=False)

    codeforces_api_key = Column(String(100))
    codeforces_api_secret = Column(String(100))

    yandex_access_token = Column(String(255))

    refresh_token = relationship("RefreshToken", back_populates="user")
    contests = relationship("Contest", back_populates="user")
    participants = relationship("Participant", back_populates="user")
    role =relationship("Role", back_populates="user")


