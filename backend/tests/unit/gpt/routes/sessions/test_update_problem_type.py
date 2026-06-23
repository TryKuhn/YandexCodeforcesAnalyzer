"""Unit tests for routes.sessions.update_problem_type.update_problem_type."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import UpdateProblemTypeRequest
from api.user.gpt.routes.sessions import update_problem_type as mod
from api.user.gpt.routes.sessions.update_problem_type import update_problem_type
from models.task.session import ProblemType


@pytest.fixture
def captured_push(monkeypatch):
    """Stub the Polygon update_info/commit so no network is hit; capture calls."""
    calls = []

    async def fake_update_info(*, problem_id, user_id, db, interactive=None, **kw):
        calls.append({"problem_id": problem_id, "interactive": interactive})

    async def fake_commit(*a, **k):
        return None

    monkeypatch.setattr(mod, "update_info", fake_update_info)
    monkeypatch.setattr(mod, "commit_changes", fake_commit)
    return calls


@pytest.mark.asyncio
async def test_switch_to_interactive_sets_flag_and_pushes(db, user, task_session, captured_push):
    req = UpdateProblemTypeRequest(problem_type="interactive")
    res = await update_problem_type(task_session.id, req, user_id=user.id, db=db)
    assert res["problem_type"] == ProblemType.INTERACTIVE
    assert res["problem_settings"]["interactive"] is True
    assert res["problem_settings"].get("enable_points") in (None, False)
    assert captured_push == [{"problem_id": 555, "interactive": True}]


@pytest.mark.asyncio
async def test_switch_to_output_only_forces_points_and_clears_interactive(
    db, user, task_session, captured_push
):
    req = UpdateProblemTypeRequest(problem_type="output_only")
    res = await update_problem_type(task_session.id, req, user_id=user.id, db=db)
    assert res["problem_type"] == ProblemType.OUTPUT_ONLY
    assert res["problem_settings"]["enable_points"] is True
    assert res["problem_settings"]["interactive"] is False
    assert captured_push == [{"problem_id": 555, "interactive": False}]


@pytest.mark.asyncio
async def test_switch_to_regular_clears_interactive_on_polygon(
    db, user, task_session, captured_push
):
    req = UpdateProblemTypeRequest(problem_type="regular")
    res = await update_problem_type(task_session.id, req, user_id=user.id, db=db)
    assert res["problem_type"] == ProblemType.REGULAR
    assert res["problem_settings"]["interactive"] is False
    # The fix: switching away from interactive must clear the flag on Polygon.
    assert captured_push == [{"problem_id": 555, "interactive": False}]


@pytest.mark.asyncio
async def test_no_polygon_push_when_problem_not_created(db, user, task_session, captured_push):
    task_session.polygon_problem_id = None
    await db.commit()
    req = UpdateProblemTypeRequest(problem_type="interactive")
    await update_problem_type(task_session.id, req, user_id=user.id, db=db)
    assert captured_push == []


@pytest.mark.asyncio
async def test_update_problem_type_404(db, user, captured_push):
    req = UpdateProblemTypeRequest(problem_type="regular")
    with pytest.raises(HTTPException) as exc:
        await update_problem_type("nope", req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
