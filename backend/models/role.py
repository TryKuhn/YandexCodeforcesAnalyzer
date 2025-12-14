from sqlalchemy import Column, Integer, String

from backend.models.base import Base

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key = True)
    rolename = Column(String(100), nullable=False)