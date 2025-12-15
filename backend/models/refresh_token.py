from sqlalchemy import Column, DateTime, Integer, String

from models.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)

    refresh_token = Column(String(256), unique=True, nullable=False)
    expires_in = Column(DateTime, nullable=False)
