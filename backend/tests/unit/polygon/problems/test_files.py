"""Unit tests for api/user/polygon/problems/files.py route handlers."""
import pytest
from fastapi import HTTPException

import api.user.polygon.problems.files as mod
from api.pydantic_schemas.user.polygon_task import (
    SaveFileRequest,
    SaveScriptRequest,
    SaveSolutionRequest,
    SetCheckerRequest,
    SetValidatorRequest,
)
from api.user.polygon.get_response import PolygonAPIError
from api.user.polygon.problems.files import (
    route_get_checker,
    route_get_files,
    route_get_script,
    route_get_validator,
    route_save_file,
    route_save_script,
    route_save_solution,
    route_set_checker,
    route_set_validator,
    route_view_file,
    route_view_solution,
)


@pytest.mark.asyncio
async def test_route_get_files_merges_solutions(monkeypatch, db, user):
    async def fake_get_files(problem_id, user_id, db):
        return {"resource": ["a"], "source": ["b"]}

    async def fake_get_solutions(problem_id, user_id, db):
        return [{"name": "sol.cpp"}]

    monkeypatch.setattr(mod, "get_files", fake_get_files)
    monkeypatch.setattr(mod, "get_solutions", fake_get_solutions)

    result = await route_get_files(polygon_id=555, user_id=user.id, db=db)
    assert result["resource"] == ["a"]
    assert result["solutions"] == [{"name": "sol.cpp"}]


@pytest.mark.asyncio
async def test_route_get_files_non_dict_non_list(monkeypatch, db, user):
    async def fake_get_files(problem_id, user_id, db):
        return "oops"

    async def fake_get_solutions(problem_id, user_id, db):
        return {"not": "a list"}

    monkeypatch.setattr(mod, "get_files", fake_get_files)
    monkeypatch.setattr(mod, "get_solutions", fake_get_solutions)

    result = await route_get_files(polygon_id=555, user_id=user.id, db=db)
    assert result == {"solutions": []}


@pytest.mark.asyncio
async def test_route_view_file_ok(monkeypatch, db, user):
    async def fake_view_file(problem_id, file_type, name, user_id, db):
        return "content-here"

    monkeypatch.setattr(mod, "view_file", fake_view_file)
    result = await route_view_file(
        polygon_id=555, type="source", name="a.cpp", user_id=user.id, db=db
    )
    assert result == {"content": "content-here"}


@pytest.mark.asyncio
async def test_route_view_file_404(monkeypatch, db, user):
    async def fake_view_file(problem_id, file_type, name, user_id, db):
        raise PolygonAPIError("missing")

    monkeypatch.setattr(mod, "view_file", fake_view_file)
    with pytest.raises(HTTPException) as exc:
        await route_view_file(
            polygon_id=555, type="source", name="x", user_id=user.id, db=db
        )
    assert exc.value.status_code == 404
    assert "missing" in exc.value.detail


@pytest.mark.asyncio
async def test_route_save_file(monkeypatch, db, user):
    captured = {}

    async def fake_save_file(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(mod, "save_file", fake_save_file)
    body = SaveFileRequest(type="source", name="a.cpp", content="int main(){}")
    result = await route_save_file(polygon_id=555, body=body, user_id=user.id, db=db)
    assert result == {"ok": True}
    assert captured["file_type"] == "source"
    assert captured["name"] == "a.cpp"
    assert captured["file_content"] == "int main(){}"


@pytest.mark.asyncio
async def test_route_view_solution_ok(monkeypatch, db, user):
    async def fake_view_solution(problem_id, name, user_id, db):
        return "sol"

    monkeypatch.setattr(mod, "view_solution", fake_view_solution)
    result = await route_view_solution(
        polygon_id=555, name="sol.cpp", user_id=user.id, db=db
    )
    assert result == {"content": "sol"}


@pytest.mark.asyncio
async def test_route_view_solution_404(monkeypatch, db, user):
    async def fake_view_solution(problem_id, name, user_id, db):
        raise PolygonAPIError("nope")

    monkeypatch.setattr(mod, "view_solution", fake_view_solution)
    with pytest.raises(HTTPException) as exc:
        await route_view_solution(
            polygon_id=555, name="sol.cpp", user_id=user.id, db=db
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_route_save_solution(monkeypatch, db, user):
    captured = {}

    async def fake_save_solution(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(mod, "save_solution", fake_save_solution)
    body = SaveSolutionRequest(name="sol.cpp", content="code", tag="MA")
    result = await route_save_solution(polygon_id=555, body=body, user_id=user.id, db=db)
    assert result == {"ok": True}
    assert captured["tag"] == "MA"
    assert captured["file_content"] == "code"


@pytest.mark.asyncio
async def test_route_get_and_set_checker(monkeypatch, db, user):
    async def fake_get_checker(problem_id, user_id, db):
        return "std::check"

    captured = {}

    async def fake_set_checker(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(mod, "get_checker", fake_get_checker)
    monkeypatch.setattr(mod, "set_checker", fake_set_checker)

    got = await route_get_checker(polygon_id=555, user_id=user.id, db=db)
    assert got == {"checker": "std::check"}

    body = SetCheckerRequest(name="chk.cpp", content="x")
    res = await route_set_checker(polygon_id=555, body=body, user_id=user.id, db=db)
    assert res == {"ok": True}
    assert captured["name"] == "chk.cpp"


@pytest.mark.asyncio
async def test_route_get_and_set_validator(monkeypatch, db, user):
    async def fake_get_validator(problem_id, user_id, db):
        return "val"

    captured = {}

    async def fake_set_validator(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(mod, "get_validator", fake_get_validator)
    monkeypatch.setattr(mod, "set_validator", fake_set_validator)

    got = await route_get_validator(polygon_id=555, user_id=user.id, db=db)
    assert got == {"validator": "val"}

    body = SetValidatorRequest(name="val.cpp", content="y")
    res = await route_set_validator(polygon_id=555, body=body, user_id=user.id, db=db)
    assert res == {"ok": True}
    assert captured["file_content"] == "y"


@pytest.mark.asyncio
async def test_route_get_and_save_script(monkeypatch, db, user):
    async def fake_get_script(problem_id, testset, user_id, db):
        return "gen 1 > 1"

    captured = {}

    async def fake_save_script(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(mod, "get_script", fake_get_script)
    monkeypatch.setattr(mod, "save_script", fake_save_script)

    got = await route_get_script(
        polygon_id=555, testset="tests", user_id=user.id, db=db
    )
    assert got == {"content": "gen 1 > 1"}

    body = SaveScriptRequest(source="gen 2 > 2")
    res = await route_save_script(
        polygon_id=555, testset="tests", body=body, user_id=user.id, db=db
    )
    assert res == {"ok": True}
    assert captured["source"] == "gen 2 > 2"
    assert captured["testset"] == "tests"
