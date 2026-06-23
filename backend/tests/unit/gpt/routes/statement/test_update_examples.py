"""Unit tests for routes.statement.update_examples.update_examples."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import UpdateExamplesRequest
from api.user.gpt.routes.statement.update_examples import update_examples


@pytest.mark.asyncio
async def test_update_examples_overwrites(db, user, task_session):
    task_session.examples = [{"index": "1", "input": "old", "output": "old"}]
    await db.commit()

    examples = [{"index": "1", "input": "a", "output": "b"},
                {"index": "2", "input": "c", "output": "d"}]
    req = UpdateExamplesRequest(session_id=task_session.id, examples=examples)
    res = await update_examples(task_session.id, req, user_id=user.id, db=db)
    assert res["examples"] == examples
    await db.refresh(task_session)
    assert task_session.examples == examples


@pytest.mark.asyncio
async def test_update_examples_404(db, user):
    req = UpdateExamplesRequest(session_id="nope", examples=[])
    with pytest.raises(HTTPException) as exc:
        await update_examples("nope", req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
