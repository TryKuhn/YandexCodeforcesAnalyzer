from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import relationship, Mapped, mapped_column

from models.base import Base

if TYPE_CHECKING:
    from models.refresh_token import RefreshToken
    from models.contest import Contest
    from models.participant import Participant
    from models.role import Role

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)

    login: Mapped[str] = mapped_column(String(50), unique=True)
    password: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(100))

    codeforces_api_key: Mapped[str | None] = mapped_column(String(100))
    codeforces_api_secret: Mapped[str | None] = mapped_column(String(100))

    yandex_access_token: Mapped[str | None] = mapped_column(String(255))

    refresh_tokens: Mapped[list['RefreshToken']] = relationship(
        back_populates='user',
        cascade='all, delete-orphan'
    )
    contests: Mapped[list['Contest']] = relationship(
        back_populates='user',
        cascade='all, delete-orphan'
    )
    participants: Mapped[list['Participant']] = relationship(
        back_populates='user',
        cascade='all, delete-orphan'
    )
    roles: Mapped[list['Role']] = relationship(
        back_populates='user',
        cascade='all, delete-orphan'
    )
