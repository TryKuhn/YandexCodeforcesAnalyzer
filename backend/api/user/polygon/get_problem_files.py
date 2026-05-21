from time import time

from aiohttp import ClientSession
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.user.polygon.create_signature import create_signature
from api.user.polygon.get_response import get_response, PolygonAPIError
from models import User
from settings import settings


async def _polygon_call(method_name: str, params: dict, user: User) -> any:
    params = {
        "apiKey": user.polygon_api_key,
        "time": str(int(time())),
        **params,
    }
    signature = create_signature(method_name, params, user.polygon_api_secret)
    params["apiSig"] = signature
    url = URL(settings.POLYGON_HOST) / method_name
    async with ClientSession() as client:
        try:
            return await get_response(client, url, params)
        except PolygonAPIError as e:
            raise HTTPException(status_code=400, detail=f"Polygon error: {e}")


async def _get_user(user_id: int, db: AsyncSession) -> User:
    r = await db.execute(select(User).filter_by(id=user_id))
    user = r.scalars().first()
    if not user or not user.polygon_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Polygon API is not configured")
    return user


async def get_problem_solutions(problem_id: int, user_id: int, db: AsyncSession) -> list[dict]:
    """Returns list of solution objects from Polygon."""
    user = await _get_user(user_id, db)
    return await _polygon_call("problem.solutions", {"problemId": str(problem_id)}, user) or []


async def view_solution(problem_id: int, name: str, user_id: int, db: AsyncSession) -> str:
    """Returns raw source code of a solution."""
    user = await _get_user(user_id, db)
    result = await _polygon_call("problem.viewSolution", {"problemId": str(problem_id), "name": name}, user)
    return result.get("message", "") if isinstance(result, dict) else str(result)


async def get_problem_files(problem_id: int, user_id: int, db: AsyncSession) -> dict:
    """Returns {resourceFiles, sourceFiles, auxFiles} from problem.files."""
    user = await _get_user(user_id, db)
    return await _polygon_call("problem.files", {"problemId": str(problem_id)}, user) or {}


async def view_file(problem_id: int, file_type: str, name: str, user_id: int, db: AsyncSession) -> str:
    """Returns raw content of a resource/source/aux file."""
    user = await _get_user(user_id, db)
    result = await _polygon_call(
        "problem.viewFile",
        {"problemId": str(problem_id), "type": file_type, "name": name},
        user,
    )
    return result.get("message", "") if isinstance(result, dict) else str(result)


async def get_problem_script(problem_id: int, testset: str, user_id: int, db: AsyncSession) -> str:
    """Returns the generator script for a testset."""
    user = await _get_user(user_id, db)
    result = await _polygon_call("problem.script", {"problemId": str(problem_id), "testset": testset}, user)
    return result.get("message", "") if isinstance(result, dict) else str(result)


async def get_problem_tests(problem_id: int, testset: str, user_id: int, db: AsyncSession) -> list[dict]:
    """Returns list of test objects for the given testset."""
    user = await _get_user(user_id, db)
    return await _polygon_call("problem.tests", {"problemId": str(problem_id), "testset": testset}, user) or []


async def get_test_input(problem_id: int, testset: str, test_index: int, user_id: int, db: AsyncSession) -> str:
    """Returns raw test input."""
    user = await _get_user(user_id, db)
    result = await _polygon_call(
        "problem.testInput",
        {"problemId": str(problem_id), "testset": testset, "testIndex": str(test_index)},
        user,
    )
    return result.get("message", "") if isinstance(result, dict) else str(result)


async def get_problem_tags(problem_id: int, user_id: int, db: AsyncSession) -> list[str]:
    """Returns list of tags for the problem."""
    user = await _get_user(user_id, db)
    result = await _polygon_call("problem.viewTags", {"problemId": str(problem_id)}, user)
    if isinstance(result, list):
        return result
    return []
