from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from settings import settings

engine = create_async_engine(settings.database_url)
Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with Session() as session:
        yield session
