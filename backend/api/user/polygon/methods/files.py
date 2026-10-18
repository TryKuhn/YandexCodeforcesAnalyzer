"""Problem files: resources, sources, aux."""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import PolygonParamError, call, choice
from api.user.polygon.constants import FILE_TYPES


async def get_files(problem_id: int, user_id: int, db: AsyncSession) -> dict[str, Any]:
    """``problem.files`` → ``{resourceFiles, sourceFiles, auxFiles}``."""
    result = await call("problem.files", user_id, db, problemId=problem_id)
    return result if isinstance(result, dict) else {}


async def view_file(
    problem_id: int, file_type: str, name: str, user_id: int, db: AsyncSession
) -> str:
    """``problem.viewFile`` -> file content as text."""
    method = "problem.viewFile"
    return await call(
        method, user_id, db,
        kind="text",
        problemId=problem_id,
        type=choice(file_type, FILE_TYPES, "type", method=method),
        name=name,
    )


async def view_file_bytes(
    problem_id: int, file_type: str, name: str, user_id: int, db: AsyncSession
) -> bytes:
    """``problem.viewFile`` -> raw bytes (for binary resources)."""
    method = "problem.viewFile"
    return await call(
        method, user_id, db,
        kind="bytes",
        problemId=problem_id,
        type=choice(file_type, FILE_TYPES, "type", method=method),
        name=name,
    )


async def save_file(
    problem_id: int,
    file_type: str,
    name: str,
    file: bytes | str | None,
    user_id: int,
    db: AsyncSession,
    *,
    source_type: str | None = None,
    check_existing: bool | None = None,
    for_types: str | None = None,
    stages: str | None = None,
    assets: str | None = None,
) -> None:
    """``problem.saveFile``.

    ``file=None`` edits the properties of an existing file. ``forTypes``/
    ``stages``/``assets`` are for resources only and go together
    (``for_types=""`` alone removes the advanced properties).
    """
    method = "problem.saveFile"
    file_type = choice(file_type, FILE_TYPES, "type", method=method) or ""
    advanced = (for_types, stages, assets)
    if any(v is not None for v in advanced):
        if file_type != "resource":
            raise PolygonParamError(
                "forTypes/stages/assets допустимы только для type=resource", method=method
            )
        if for_types is None or (for_types != "" and None in advanced):
            raise PolygonParamError(
                "forTypes, stages и assets задаются только вместе", method=method
            )
    await call(
        method, user_id, db,
        problemId=problem_id,
        type=file_type,
        name=name,
        file=file,
        sourceType=source_type,
        checkExisting=check_existing,
        forTypes=for_types,
        stages=stages,
        assets=assets,
    )
