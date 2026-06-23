"""Unit tests for routes.statement.update_field.update_statement_field."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import UpdateStatementFieldRequest
from api.user.gpt.routes.statement.update_field import update_statement_field


@pytest.mark.asyncio
async def test_update_field_happy(db, user, task_session):
    task_session.statement = {"name": "Old", "legend": "L"}
    await db.commit()

    req = UpdateStatementFieldRequest(
        session_id=task_session.id, field="name", value="New Name"
    )
    res = await update_statement_field(task_session.id, req, user_id=user.id, db=db)
    assert res["field"] == "name"
    assert res["value"] == "New Name"
    await db.refresh(task_session)
    assert task_session.statement["name"] == "New Name"
    assert task_session.statement["legend"] == "L"


@pytest.mark.asyncio
async def test_update_field_no_statement_400(db, user, task_session):
    req = UpdateStatementFieldRequest(
        session_id=task_session.id, field="name", value="x"
    )
    with pytest.raises(HTTPException) as exc:
        await update_statement_field(task_session.id, req, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_update_field_disallowed_400(db, user, task_session):
    task_session.statement = {"name": "P"}
    await db.commit()
    req = UpdateStatementFieldRequest(
        session_id=task_session.id, field="secret", value="x"
    )
    with pytest.raises(HTTPException) as exc:
        await update_statement_field(task_session.id, req, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_update_field_404(db, user):
    req = UpdateStatementFieldRequest(session_id="nope", field="name", value="x")
    with pytest.raises(HTTPException) as exc:
        await update_statement_field("nope", req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
