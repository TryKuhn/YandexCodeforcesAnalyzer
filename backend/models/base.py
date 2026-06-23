"""Declarative base class for all ORM models."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base inherited by every ORM model."""
    pass
