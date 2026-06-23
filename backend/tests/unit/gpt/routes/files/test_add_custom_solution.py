"""Unit tests for routes.files.add_custom_solution.add_custom_solution."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import AddCustomSolutionRequest
from api.user.gpt.routes.files.add_custom_solution import add_custom_solution
from api.user.gpt.services.ai_file_helpers import get_session_files


@pytest.mark.asyncio
async def test_add_custom_solution_happy(db, user, task_session):
    req = AddCustomSolutionRequest(session_id=task_session.id, tag="WA", name="brute")
    res = await add_custom_solution(req, user_id=user.id, db=db)

    file_type = res["file_type"]
    assert file_type.startswith("sol_custom_")
    assert res["name"] == "brute.cpp"
    assert res["tag"] == "WA"
    assert res["solution_meta"][file_type] == {"tag": "WA", "name": "brute.cpp"}

    files = await get_session_files(db, task_session.id)
    assert file_type in files
    await db.refresh(task_session)
    assert file_type in task_session.solution_meta


@pytest.mark.asyncio
async def test_add_custom_solution_keeps_cpp_extension(db, user, task_session):
    req = AddCustomSolutionRequest(session_id=task_session.id, tag="OK", name="x.cpp")
    res = await add_custom_solution(req, user_id=user.id, db=db)
    assert res["name"] == "x.cpp"


@pytest.mark.asyncio
async def test_add_custom_solution_404(db, user):
    req = AddCustomSolutionRequest(session_id="nope", tag="OK", name="x")
    with pytest.raises(HTTPException) as exc:
        await add_custom_solution(req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
