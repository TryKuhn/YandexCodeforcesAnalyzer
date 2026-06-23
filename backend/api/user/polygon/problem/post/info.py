from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def update_info(
    problem_id: int,
    user_id: int,
    db: AsyncSession,
    input_file: Optional[str] = None,
    output_file: Optional[str] = None,
    interactive: Optional[bool] = None,
    well_formed: Optional[bool] = None,
    time_limit: Optional[int] = None,
    memory_limit: Optional[int] = None,
):
    """Update problem metadata via problem.updateInfo, sending only provided fields.

    Booleans are serialized as ``"true"``/``"false"`` and numeric limits as strings,
    matching Polygon's expected parameter format.
    """
    user = await get_user(user_id, db)
    params: dict = {"problemId": str(problem_id)}

    if input_file is not None:
        params["inputFile"] = input_file
    if output_file is not None:
        params["outputFile"] = output_file
    if interactive is not None:
        params["interactive"] = "true" if interactive else "false"
    if well_formed is not None:
        params["wellFormed"] = "true" if well_formed else "false"
    if time_limit is not None:
        params["timeLimit"] = str(time_limit)
    if memory_limit is not None:
        params["memoryLimit"] = str(memory_limit)

    return await polygon_call("problem.updateInfo", params, user)
