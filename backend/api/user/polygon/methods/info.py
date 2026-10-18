"""Problem properties: info, note, tags, general description/tutorial, access."""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import PolygonParamError, call, choice
from api.user.polygon.constants import (ACCESS_TYPES, MEMORY_LIMIT_RANGE,
                                        TIME_LIMIT_RANGE)


async def get_info(problem_id: int, user_id: int, db: AsyncSession) -> dict[str, Any]:
    """``problem.info`` -> ``ProblemInfo``."""
    return await call("problem.info", user_id, db, problemId=problem_id)


def _check_limits(time_limit: int | None, memory_limit: int | None) -> None:
    method = "problem.updateInfo"
    if time_limit is not None:
        low, high = TIME_LIMIT_RANGE
        if not (low <= time_limit <= high) or time_limit % 50:
            raise PolygonParamError(
                f"timeLimit: {time_limit} мс вне диапазона {low}–{high} или не кратно 50",
                method=method,
            )
    if memory_limit is not None:
        low, high = MEMORY_LIMIT_RANGE
        if not (low <= memory_limit <= high):
            raise PolygonParamError(
                f"memoryLimit: {memory_limit} МБ вне диапазона {low}–{high}", method=method
            )


async def update_info(
    problem_id: int,
    user_id: int,
    db: AsyncSession,
    *,
    input_file: str | None = None,
    output_file: str | None = None,
    interactive: bool | None = None,
    well_formed: bool | None = None,
    skip_duplicated_tests_validation: bool | None = None,
    time_limit: int | None = None,
    memory_limit: int | None = None,
) -> None:
    """``problem.updateInfo`` -- only the given fields are sent."""
    _check_limits(time_limit, memory_limit)
    await call(
        "problem.updateInfo", user_id, db,
        problemId=problem_id,
        inputFile=input_file,
        outputFile=output_file,
        interactive=interactive,
        wellFormed=well_formed,
        skipDuplicatedTestsValidation=skip_duplicated_tests_validation,
        timeLimit=time_limit,
        memoryLimit=memory_limit,
    )


async def get_note(problem_id: int, user_id: int, db: AsyncSession) -> str:
    """``problem.note`` -> the note text."""
    return await call("problem.note", user_id, db, problemId=problem_id) or ""


async def save_note(problem_id: int, note: str, user_id: int, db: AsyncSession) -> None:
    """``problem.saveNote`` (up to 50 chars; an empty string clears it)."""
    if len(note) > 50:
        raise PolygonParamError("note: не длиннее 50 символов", method="problem.saveNote")
    await call("problem.saveNote", user_id, db, problemId=problem_id, note=note)


async def view_tags(problem_id: int, user_id: int, db: AsyncSession) -> list[str]:
    """``problem.viewTags`` -> list of tags."""
    result = await call("problem.viewTags", user_id, db, problemId=problem_id)
    return result if isinstance(result, list) else []


async def save_tags(
    problem_id: int, tags: list[str], user_id: int, db: AsyncSession
) -> None:
    """``problem.saveTags`` -- replaces all tags of the problem."""
    await call("problem.saveTags", user_id, db, problemId=problem_id, tags=list(tags))


async def view_general_description(
    problem_id: int, user_id: int, db: AsyncSession
) -> str:
    """``problem.viewGeneralDescription``."""
    return await call("problem.viewGeneralDescription", user_id, db, problemId=problem_id) or ""


async def save_general_description(
    problem_id: int, description: str, user_id: int, db: AsyncSession
) -> None:
    """``problem.saveGeneralDescription``."""
    await call(
        "problem.saveGeneralDescription", user_id, db,
        problemId=problem_id, description=description,
    )


async def view_general_tutorial(problem_id: int, user_id: int, db: AsyncSession) -> str:
    """``problem.viewGeneralTutorial``."""
    return await call("problem.viewGeneralTutorial", user_id, db, problemId=problem_id) or ""


async def save_general_tutorial(
    problem_id: int, tutorial: str, user_id: int, db: AsyncSession
) -> None:
    """``problem.saveGeneralTutorial``."""
    await call(
        "problem.saveGeneralTutorial", user_id, db, problemId=problem_id, tutorial=tutorial
    )


async def get_accesses(
    problem_id: int, user_id: int, db: AsyncSession
) -> list[dict[str, Any]]:
    """``problem.accesses`` -> ``ProblemAccess[]`` (needs WRITE/OWNER)."""
    result = await call("problem.accesses", user_id, db, problemId=problem_id)
    return result if isinstance(result, list) else []


async def set_access(
    problem_id: int, login: str, access_type: str, user_id: int, db: AsyncSession
) -> None:
    """``problem.setAccess`` -- READ / WRITE / NONE for a login (not a group)."""
    method = "problem.setAccess"
    if login.startswith("@"):
        raise PolygonParamError("login: группы (@...) не поддерживаются", method=method)
    await call(
        method, user_id, db,
        problemId=problem_id,
        login=login,
        accessType=choice(access_type, ACCESS_TYPES, "accessType", method=method),
    )
