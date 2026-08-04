"""Content-addressed blob: bytes live in S3/MinIO under their sha256, this row counts users."""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Blob(Base):
    """Refcount is what makes dedup safe: delete only when nobody references the hash."""
    __tablename__ = "blobs"

    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    size: Mapped[int] = mapped_column(BigInteger)
    refcount: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
