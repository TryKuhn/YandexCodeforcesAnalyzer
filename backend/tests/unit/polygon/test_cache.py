"""Tests for api.user.polygon.cache — Polygon fetch + local upsert."""
from sqlalchemy import select

from api.user.polygon import cache
from models.task.problem import PolygonProblem
from models.task.solution import PolygonSolution
from models.task.statement import PolygonStatement


async def _problem(db, user, polygon_id=555, **kw):
    p = PolygonProblem(user_id=user.id, polygon_id=polygon_id, owner="o", name="n", **kw)
    db.add(p)
    await db.commit()
    return p


# --- problem list ---------------------------------------------------------------
async def test_refresh_problem_list_inserts_and_updates(polygon_api, db, user):
    await _problem(db, user, polygon_id=5, revision=1)
    data = [
        {"id": 1, "owner": "o", "name": "p1", "accessType": "OWNER", "revision": 2,
         "workingCopyRevision": 3, "latestPackage": 4, "favourite": True, "modified": True},
        {"id": 5, "owner": "new", "name": "renamed", "revision": 9},
        {"id": None},  # skipped — no id
    ]
    polygon_api.respond("problems.list", data)

    assert await cache.refresh_problem_list(user.id, db) == data

    rows = {p.polygon_id: p for p in (await db.execute(select(PolygonProblem))).scalars()}
    assert set(rows) == {1, 5}
    assert rows[1].favourite is True and rows[1].access_type == "OWNER"
    assert rows[1].list_fetched_at is not None
    assert (rows[5].name, rows[5].owner, rows[5].revision) == ("renamed", "new", 9)


async def test_refresh_problem_list_show_deleted(polygon_api, db, user):
    polygon_api.respond("problems.list", [])
    await cache.refresh_problem_list(user.id, db, show_deleted=True)
    assert polygon_api.last().params == {"showDeleted": "true"}
    await cache.refresh_problem_list(user.id, db)
    assert polygon_api.last().params == {}


async def test_refresh_problem_list_does_not_touch_other_users(polygon_api, db, user):
    from models.user.user import User

    other = User(login="x", password="x", email="x@x", role_id=user.role_id)
    db.add(other)
    await db.commit()
    db.add(PolygonProblem(user_id=other.id, polygon_id=1, owner="theirs", name="theirs"))
    await db.commit()

    polygon_api.respond("problems.list", [{"id": 1, "owner": "mine", "name": "mine"}])
    await cache.refresh_problem_list(user.id, db)

    rows = (await db.execute(select(PolygonProblem).filter_by(polygon_id=1))).scalars().all()
    assert sorted((r.user_id, r.name) for r in rows) == sorted(
        [(other.id, "theirs"), (user.id, "mine")]
    )


# --- info -------------------------------------------------------------------------
async def test_refresh_problem_info_updates_cached_row(polygon_api, db, user):
    p = await _problem(db, user)
    polygon_api.respond("problem.info", {
        "inputFile": "in.txt", "outputFile": "out.txt", "interactive": True,
        "wellFormed": True, "timeLimit": 1500, "memoryLimit": 128,
    })
    info = await cache.refresh_problem_info(555, user.id, db)
    assert info["timeLimit"] == 1500
    await db.refresh(p)
    assert (p.input_file, p.output_file, p.interactive, p.well_formed) == (
        "in.txt", "out.txt", True, True)
    assert (p.time_limit, p.memory_limit) == (1500, 128)
    assert p.info_fetched_at is not None


async def test_refresh_problem_info_without_cached_row(polygon_api, db, user):
    polygon_api.respond("problem.info", {"timeLimit": 1000})
    assert await cache.refresh_problem_info(1, user.id, db) == {"timeLimit": 1000}


# --- statements ---------------------------------------------------------------------
async def test_refresh_statements_upserts_languages(polygon_api, db, user):
    p = await _problem(db, user)
    db.add(PolygonStatement(problem_id=p.id, lang="russian", name="old"))
    await db.commit()
    polygon_api.respond("problem.statements", {
        "russian": {"name": "Сумма", "legend": "L", "scoring": "S"},
        "english": {"name": "Sum", "encoding": "utf-8"},
    })

    result = await cache.refresh_statements(555, user.id, db)
    assert set(result) == {"russian", "english"}

    rows = {s.lang: s for s in (await db.execute(select(PolygonStatement))).scalars()}
    assert set(rows) == {"russian", "english"}
    assert rows["russian"].name == "Сумма" and rows["russian"].scoring == "S"
    assert rows["english"].name == "Sum"


async def test_refresh_statements_uncached_problem_only_returns(polygon_api, db, user):
    polygon_api.respond("problem.statements", {"russian": {"name": "x"}})
    assert await cache.refresh_statements(1, user.id, db) == {"russian": {"name": "x"}}
    assert (await db.execute(select(PolygonStatement))).scalars().all() == []


# --- solutions ------------------------------------------------------------------------
async def test_refresh_solutions_upserts_metadata(polygon_api, db, user):
    p = await _problem(db, user)
    db.add(PolygonSolution(problem_id=p.id, name="main.cpp", content="keep", tag="OK"))
    await db.commit()
    polygon_api.respond("problem.solutions", [
        {"name": "main.cpp", "tag": "MA", "sourceType": "cpp.g++17"},
        {"name": "wa.py", "tag": "WA", "sourceType": "python.3"},
    ])

    await cache.refresh_solutions(555, user.id, db)

    rows = {s.name: s for s in (await db.execute(select(PolygonSolution))).scalars()}
    assert rows["main.cpp"].tag == "MA" and rows["main.cpp"].content == "keep"
    assert rows["wa.py"].uploaded is True and rows["wa.py"].content == ""
