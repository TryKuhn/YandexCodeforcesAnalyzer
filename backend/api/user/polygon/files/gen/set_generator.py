from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.files.gen.add_source_file import add_source


async def set_generator(
    problem_id: int, name: str, generator_file: str, user_id: int, db: AsyncSession
):
    return await add_source(problem_id, name, generator_file, user_id, db)
