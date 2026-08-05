"""Declarative base class for all ORM models."""
from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """Naive UTC, like the rest of the server."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Shared declarative base inherited by every ORM model."""
    pass
