from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.polygon import polygon_router, add_source
from app.database import get_db


@polygon_router.post('/set_generator')
async def set_generator(
        problem_id: int,
        name: str,
        generator_file: str,
        user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await add_source(problem_id, name, generator_file, user_id, db)
