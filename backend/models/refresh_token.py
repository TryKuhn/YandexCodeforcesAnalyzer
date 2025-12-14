from sqlalchemy import Column, Integer, String, DateTime

from backend.models.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)

    refresh_token_hash = Column(String(256), unique=True, nullable=False)

    expires_in = Column(DateTime, nullable=False)
