from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from models.base import Base


class User(Base):
    __tablename__ = "users"

    login = Column(String(50), primary_key=True, nullable=False)
    password = Column(String(120), nullable=False)
    email = Column(String(50), nullable=False)

    codeforces_api_key = Column(String(100), nullable=True)
    codeforces_api_secret = Column(String(100), nullable=True)

    yandex_access_token = Column(String(255), nullable=True)

    refresh_token = relationship("RefreshToken", back_populates="users")
    contests = relationship("Contest", back_populates="users")
    participants = relationship("Participant", back_populates="users")
    role = relationship("Role", back_populates="users")
