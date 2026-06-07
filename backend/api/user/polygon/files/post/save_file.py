from typing import Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def save_file(
    problem_id: int,
    file_type: str,
    name: str,
    file_content: Union[bytes, str],
    user_id: int,
    db: AsyncSession,
    source_type: Optional[str] = None,
    check_existing: Optional[bool] = None,
    for_types: Optional[str] = None,
    stages: Optional[str] = None,
    assets: Optional[str] = None,
):
    """Add or edit resource, source or aux file (problem.saveFile).

    file_type: 'resource' | 'source' | 'aux'
    For resource files, forTypes/stages/assets must all be present or all absent.
    """
    user = await get_user(user_id, db)
    params: dict = {
        "problemId": str(problem_id),
        "type": file_type,
        "name": name,
        "file": file_content,
    }
    if source_type:
        params["sourceType"] = source_type
    if check_existing is not None:
        params["checkExisting"] = "true" if check_existing else "false"
    if file_type == "resource" and for_types is not None:
        params["forTypes"] = for_types
        params["stages"] = stages or ""
        params["assets"] = assets or ""
    return await polygon_call("problem.saveFile", params, user)
