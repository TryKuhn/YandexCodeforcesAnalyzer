"""Unit tests for the chat context resolver (services.chat.context_resolver)."""
import pytest

from api.pydantic_schemas.user.ai_task import ChatContext
from api.user.gpt.services.ai_file_helpers import upsert_ai_file
from api.user.gpt.services.chat import context_resolver as cr


@pytest.mark.asyncio
async def test_resolve_statement_scope(db, task_session):
    out = await cr.resolve(db, task_session, ChatContext(scope="statement"))
    assert out.scope == "statement"
    assert out.file_key is None
    assert out.candidates == []


@pytest.mark.asyncio
async def test_resolve_file_scope_with_key(db, task_session):
    out = await cr.resolve(db, task_session, ChatContext(scope="file", file_key="checker"))
    assert out.scope == "file"
    assert out.file_key == "checker"
    assert out.candidates == ["checker"]


@pytest.mark.asyncio
async def test_resolve_file_scope_without_key(db, task_session):
    out = await cr.resolve(db, task_session, ChatContext(scope="file", file_key=None))
    assert out.scope == "file"
    assert out.file_key is None
    assert out.candidates == []


@pytest.mark.asyncio
async def test_resolve_task_scope_collects_db_files(db, task_session):
    await upsert_ai_file(db, task_session.id, "checker", "int main(){}")
    await upsert_ai_file(db, task_session.id, "validator", "int main(){}")
    await db.commit()

    out = await cr.resolve(db, task_session, ChatContext(scope="task"))
    assert out.scope == "task"
    assert set(out.candidates) == {"checker", "validator"}


@pytest.mark.asyncio
async def test_resolve_task_scope_no_files(db, task_session):
    out = await cr.resolve(db, task_session, ChatContext(scope="task"))
    assert out.scope == "task"
    assert out.candidates == []
