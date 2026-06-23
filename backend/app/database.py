"""Async SQLAlchemy engine, session factory, and request-scoped DB dependency."""
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)

from settings import settings

engine = create_async_engine(settings.database_url)
Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """Yield an async database session, closing it when the request finishes."""
    async with Session() as session:
        yield session
