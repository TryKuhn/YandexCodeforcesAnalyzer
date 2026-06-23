"""POST /import-from-polygon-full — session from a Polygon problem + its files."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import ImportFromPolygonFullRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.import_session import import_full
from api.user.gpt.services.llm.models import normalize_model
from app.database import get_db


@gpt_router.post("/import-from-polygon-full")
async def import_from_polygon_full(
    request: ImportFromPolygonFullRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a session from a Polygon problem, optionally importing its files."""
    return await import_full(
        db,
        user_id,
        problem_id=request.polygon_problem_id,
        model=normalize_model(request.model),
        load_files=bool(request.load_files),
    )
