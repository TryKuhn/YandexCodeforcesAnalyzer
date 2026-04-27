from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

if TYPE_CHECKING:
    from models.contest.contest import Contest
    from models.participant.participant import Participant
    from models.user.refresh_token import RefreshToken
    from models.user.role import Role


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))

    login: Mapped[str] = mapped_column(String(50), unique=True)
    password: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(100))

    codeforces_api_key: Mapped[str | None] = mapped_column(String(100))
    codeforces_api_secret: Mapped[str | None] = mapped_column(String(100))

    # codeforces_access_token: Mapped[str | None] = mapped_column(String(255))

    polygon_api_key: Mapped[str | None] = mapped_column(String(100))
    polygon_api_secret: Mapped[str | None] = mapped_column(String(100))

    yandex_access_token: Mapped[str | None] = mapped_column(String(255))

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    contests: Mapped[list["Contest"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    participants: Mapped[list["Participant"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    role: Mapped["Role"] = relationship(back_populates="user")
