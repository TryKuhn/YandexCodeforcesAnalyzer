"""Unit tests for api/user/polygon/problems/statement.py route handlers."""

from api.pydantic_schemas.user.polygon_task import SaveStatementRequest
from api.user.polygon.problems.statement import (
    route_get_statement_resources, route_get_statements, route_render_statements,
    route_save_statement, route_save_statement_resource,
    route_view_statement_resource)
from models.task.problem import PolygonProblem
from models.task.statement import PolygonStatement


async def _seed_problem(db, user, polygon_id=555):
    p = PolygonProblem(user_id=user.id, polygon_id=polygon_id, owner="o", name="n")
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def _seed_statement(db, p, name="Имя"):
    db.add(PolygonStatement(
        problem_id=p.id, lang="russian", encoding="utf-8",
        name=name, legend="Условие", input="Ввод", output="Вывод",
    ))
    await db.commit()


async def test_route_get_statements_from_cache(polygon_api, db, user):
    p = await _seed_problem(db, user)
    await _seed_statement(db, p)

    result = await route_get_statements(polygon_id=555, user_id=user.id, db=db)
    assert result["russian"]["name"] == "Имя"
    assert result["russian"]["legend"] == "Условие"
    assert polygon_api.calls == []


async def test_route_get_statements_refresh_bypasses_cache(polygon_api, db, user):
    p = await _seed_problem(db, user)
    await _seed_statement(db, p, name="old")
    polygon_api.respond("problem.statements", {"russian": {"name": "new"}})

    result = await route_get_statements(polygon_id=555, refresh=True, user_id=user.id, db=db)
    assert result == {"russian": {"name": "new"}}
    cached = await route_get_statements(polygon_id=555, user_id=user.id, db=db)
    assert cached["russian"]["name"] == "new"


async def test_route_get_statements_falls_back_no_problem(polygon_api, db, user):
    polygon_api.respond("problem.statements", {"english": {"name": "fetched"}})
    result = await route_get_statements(polygon_id=12345, user_id=user.id, db=db)
    assert result == {"english": {"name": "fetched"}}


async def test_route_get_statements_falls_back_no_cached_statements(polygon_api, db, user):
    await _seed_problem(db, user)
    polygon_api.respond("problem.statements", {"english": {"name": "live"}})
    result = await route_get_statements(polygon_id=555, user_id=user.id, db=db)
    assert result == {"english": {"name": "live"}}


async def test_route_save_statement_sends_and_refreshes_cache(polygon_api, db, user):
    p = await _seed_problem(db, user)
    await _seed_statement(db, p, name="old")
    polygon_api.respond("problem.statements", {"russian": {"name": "Заголовок"}})
    body = SaveStatementRequest(
        lang="russian", name="Заголовок", legend="L", input="I", output="O",
        show_in_review=True,
    )
    result = await route_save_statement(polygon_id=555, body=body, user_id=user.id, db=db)
    assert result == {"ok": True}

    assert polygon_api.methods == ["problem.saveStatement", "problem.statements"]
    assert polygon_api.calls[0].params == {
        "problemId": "555", "lang": "russian", "encoding": "utf-8", "name": "Заголовок",
        "legend": "L", "input": "I", "output": "O", "showInReview": "true",
    }
    # The cache no longer serves the pre-save statement.
    cached = await route_get_statements(polygon_id=555, user_id=user.id, db=db)
    assert cached["russian"]["name"] == "Заголовок"


async def test_route_render_statements(polygon_api, db, user):
    polygon_api.respond("problem.renderStatements", {"revision": 3, "statements": []})
    result = await route_render_statements(
        polygon_id=555, include_content=True, user_id=user.id, db=db
    )
    assert result["revision"] == 3
    assert polygon_api.last().params == {"problemId": "555", "includeContent": "true"}


async def test_route_get_statement_resources(polygon_api, db, user):
    polygon_api.respond("problem.statementResources", [{"name": "img.png"}])
    result = await route_get_statement_resources(polygon_id=555, user_id=user.id, db=db)
    assert result == [{"name": "img.png"}]


async def test_route_view_statement_resource_returns_raw_bytes(polygon_api, db, user):
    polygon_api.respond("problem.viewStatementResource", b"\x89PNG")
    response = await route_view_statement_resource(
        polygon_id=555, name="a.png", user_id=user.id, db=db
    )
    assert response.body == b"\x89PNG"
    assert response.media_type == "image/png"
    assert polygon_api.last().kind == "bytes"


async def test_route_save_statement_resource_uploads_file(polygon_api, db, user):
    class _Upload:
        filename = "pic.png"

        async def read(self):
            return b"\x89PNG\xff"

    result = await route_save_statement_resource(
        polygon_id=555, file=_Upload(), name=None, check_existing=None,
        user_id=user.id, db=db,
    )
    assert result == {"ok": True}
    assert polygon_api.last().params == {
        "problemId": "555", "name": "pic.png", "file": b"\x89PNG\xff"
    }
