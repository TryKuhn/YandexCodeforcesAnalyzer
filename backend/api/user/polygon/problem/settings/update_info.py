from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def update_info(
    problem_id: int,
    user_id: int,
    db: AsyncSession,
    input_file_name: Optional[str] = None,
    output_file_name: Optional[str] = None,
    interactive: Optional[bool] = None,
    time_limit: Optional[int] = None,
    memory_limit: Optional[int] = None,
):
    """Update problem.updateInfo. Parameter names kept for compatibility with upload_orchestrator."""
    user = await get_user(user_id, db)
    params: dict = {"problemId": str(problem_id)}

    if input_file_name:
        params["inputFile"] = input_file_name
    if output_file_name:
        params["outputFile"] = output_file_name
    if interactive is not None:
        params["interactive"] = "true" if interactive else "false"
    if time_limit:
        params["timeLimit"] = str(time_limit)
    if memory_limit:
        params["memoryLimit"] = str(memory_limit)

    return await polygon_call("problem.updateInfo", params, user)
