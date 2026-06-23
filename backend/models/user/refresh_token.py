import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.user.user import User


class RefreshToken(Base):
    """A persisted refresh-token / session record for a user."""
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    refresh_hash: Mapped[str] = mapped_column(String(256), unique=True)

    user_agent: Mapped[str | None] = mapped_column(String(255))
    last_seen: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now().replace(tzinfo=None),
        onupdate=lambda: datetime.now().replace(tzinfo=None),
    )

    created_at: Mapped[datetime] = mapped_column()
    expires_in: Mapped[datetime] = mapped_column()

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
