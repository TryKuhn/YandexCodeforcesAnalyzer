"""Unit tests for routes.files.delete_custom_solution.delete_custom_solution."""
import pytest
from fastapi import HTTPException

from api.user.gpt.routes.files.delete_custom_solution import delete_custom_solution
from api.user.gpt.services.ai_file_helpers import get_session_files, upsert_ai_file


@pytest.mark.asyncio
async def test_delete_custom_solution_happy(db, user, task_session):
    ft = "sol_custom_abcd1234"
    task_session.solution_meta = {ft: {"tag": "WA", "name": "brute.cpp"}}
    await db.commit()
    await upsert_ai_file(db, task_session.id, ft, "code",
                         solution_meta=task_session.solution_meta)
    await db.commit()

    res = await delete_custom_solution(task_session.id, ft, user_id=user.id, db=db)
    assert res["deleted"] == ft
    assert ft not in res["solution_meta"]
    files = await get_session_files(db, task_session.id)
    assert ft not in files


@pytest.mark.asyncio
async def test_delete_non_custom_400(db, user, task_session):
    with pytest.raises(HTTPException) as exc:
        await delete_custom_solution(task_session.id, "checker", user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_delete_unknown_custom_404(db, user, task_session):
    with pytest.raises(HTTPException) as exc:
        await delete_custom_solution(
            task_session.id, "sol_custom_missing", user_id=user.id, db=db
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_custom_solution_session_404(db, user):
    with pytest.raises(HTTPException) as exc:
        await delete_custom_solution("nope", "sol_custom_x", user_id=user.id, db=db)
    assert exc.value.status_code == 404
