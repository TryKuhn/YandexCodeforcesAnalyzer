from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AIGeneratedFile(Base):
    __tablename__ = "ai_generated_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("ai_sessions.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column()
    content: Mapped[str] = mapped_column(Text)
    file_type: Mapped[str] = mapped_column()
    # True = this content has been successfully uploaded to Polygon
    uploaded: Mapped[bool] = mapped_column(default=False)
