from sqlalchemy import JSON, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from backend.models.base import Base


class ContestResult(Base):
    __tablename__ = "contest_results"

    id = Column(Integer, primary_key=True)

    result_data = Column(JSON)

    user_login = Column(String(50), ForeignKey("users.login"))
    user = relationship("User", back_populates="contest_results")
