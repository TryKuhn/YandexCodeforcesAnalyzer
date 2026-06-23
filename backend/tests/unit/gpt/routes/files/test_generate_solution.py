"""Unit tests for routes.files.generate_solution.generate_solution."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import RefineFileRequest
from api.user.gpt.routes.files import generate_solution as mod
from api.user.gpt.routes.files.generate_solution import generate_solution
from api.user.gpt.services.ai_file_helpers import get_all_file_contents


@pytest.mark.asyncio
async def test_generate_solution_fixed_slot(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "P"}
    await db.commit()

    captured = {}

    async def fake_gen(tag, name, statement, model):
        captured["tag"] = tag
        captured["name"] = name
        return "int main(){}"

    monkeypatch.setattr(mod.solution_gen, "generate_for_tag", fake_gen)

    req = RefineFileRequest(
        session_id=task_session.id, file_key="solution_cpp", feedback=""
    )
    res = await generate_solution(req, user_id=user.id, db=db)
    assert res["new_code"] == "int main(){}"
    assert res["file_key"] == "solution_cpp"
    files = await get_all_file_contents(db, task_session.id)
    assert files["solution_cpp"] == "int main(){}"


@pytest.mark.asyncio
async def test_generate_solution_custom_slot(db, user, task_session, monkeypatch):
    ft = "sol_custom_deadbeef"
    task_session.statement = {"name": "P"}
    task_session.solution_meta = {ft: {"tag": "WA", "name": "brute.cpp"}}
    await db.commit()

    captured = {}

    async def fake_gen(tag, name, statement, model):
        captured["tag"] = tag
        captured["name"] = name
        return "custom code"

    monkeypatch.setattr(mod.solution_gen, "generate_for_tag", fake_gen)

    req = RefineFileRequest(session_id=task_session.id, file_key=ft, feedback="")
    res = await generate_solution(req, user_id=user.id, db=db)
    assert captured["tag"] == "WA"
    assert captured["name"] == "brute.cpp"
    assert res["new_code"] == "custom code"


@pytest.mark.asyncio
async def test_generate_solution_unknown_key_400(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "P"}
    await db.commit()
    monkeypatch.setattr(mod.solution_gen, "generate_for_tag", None)
    req = RefineFileRequest(session_id=task_session.id, file_key="mystery", feedback="")
    with pytest.raises(HTTPException) as exc:
        await generate_solution(req, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_generate_solution_no_statement_400(db, user, task_session):
    req = RefineFileRequest(
        session_id=task_session.id, file_key="solution_cpp", feedback=""
    )
    with pytest.raises(HTTPException) as exc:
        await generate_solution(req, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_generate_solution_404(db, user):
    req = RefineFileRequest(session_id="nope", file_key="solution_cpp", feedback="")
    with pytest.raises(HTTPException) as exc:
        await generate_solution(req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
