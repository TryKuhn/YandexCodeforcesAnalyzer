"""Unit tests for the LLM intent classifier (services.chat.intent_router)."""
import pytest

from api.user.gpt.services.chat import intent_router as ir


@pytest.mark.asyncio
async def test_classify_action_passthrough(stub_llm):
    stub_llm(ask={"action": "build", "file_key": None})
    out = await ir.classify_action("собери пакет", "the whole task", [])
    assert out == {"action": "build", "file_key": None}


@pytest.mark.asyncio
async def test_classify_action_drops_unknown_file_key(stub_llm):
    stub_llm(ask={"action": "edit_file", "file_key": "ghost"})
    out = await ir.classify_action("правь чекер", "ctx", ["checker"])
    # ghost not in available → file_key cleared → edit_file with no target → edit_task
    assert out == {"action": "edit_task", "file_key": None}


@pytest.mark.asyncio
async def test_classify_action_valid_file_key(stub_llm):
    stub_llm(ask={"action": "edit_file", "file_key": "checker"})
    out = await ir.classify_action("правь чекер", "ctx", ["checker"])
    assert out == {"action": "edit_file", "file_key": "checker"}


@pytest.mark.asyncio
async def test_classify_action_invalid_action_falls_back(stub_llm):
    stub_llm(ask={"action": "explode", "file_key": None})
    assert await ir.classify_action("x", "ctx", []) == {"action": "answer", "file_key": None}


@pytest.mark.asyncio
async def test_classify_action_llm_error_falls_back(monkeypatch):
    from api.user.gpt.services.llm.client import llm

    async def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(llm, "ask", boom)
    assert await ir.classify_action("x", "ctx", []) == {"action": "answer", "file_key": None}
