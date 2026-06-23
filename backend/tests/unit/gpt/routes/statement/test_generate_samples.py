"""Unit tests for routes.statement.generate_samples.generate_samples."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import GenerateSamplesRequest
from api.user.gpt.routes.statement import generate_samples as mod
from api.user.gpt.routes.statement.generate_samples import generate_samples


@pytest.mark.asyncio
async def test_generate_samples_happy(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "P"}
    await db.commit()

    captured = {}

    async def fake_gen(statement, model, count):
        captured["count"] = count
        return [{"input": "1", "output": "2"}, {"input": "3", "output": "4"}]

    monkeypatch.setattr(mod.samples_gen, "generate", fake_gen)

    req = GenerateSamplesRequest(session_id=task_session.id, count=2)
    res = await generate_samples(req, user_id=user.id, db=db)
    assert captured["count"] == 2
    assert res["examples"][0] == {"index": 1, "input": "1", "output": "2"}
    await db.refresh(task_session)
    assert task_session.examples[1]["index"] == 2


@pytest.mark.asyncio
async def test_generate_samples_no_statement_400(db, user, task_session, monkeypatch):
    monkeypatch.setattr(mod.samples_gen, "generate", None)
    req = GenerateSamplesRequest(session_id=task_session.id)
    with pytest.raises(HTTPException) as exc:
        await generate_samples(req, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_generate_samples_404(db, user):
    req = GenerateSamplesRequest(session_id="nope")
    with pytest.raises(HTTPException) as exc:
        await generate_samples(req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
