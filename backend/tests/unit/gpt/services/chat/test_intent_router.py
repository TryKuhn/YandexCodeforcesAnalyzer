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


@pytest.mark.asyncio
async def test_classify_action_retries_on_main_model(monkeypatch):
    """Regression: when the cheap router model is unavailable, classification
    must retry on the (known-good) main model instead of silently degrading to
    'answer' — otherwise a 'build me a task' request becomes a plain reply."""
    from api.user.gpt.services.llm.client import llm

    calls = []

    async def ask(model, messages, json_mode=True):
        calls.append(model)
        if model == ir.ROUTER_MODEL:
            raise RuntimeError("router model unavailable")
        return {"action": "regenerate", "file_key": None}

    monkeypatch.setattr(llm, "ask", ask)
    out = await ir.classify_action(
        "сделай задачу про qsort", "the whole task", [],
        main_model="anthropic/claude-opus-4.8",
    )
    assert out == {"action": "regenerate", "file_key": None}
    assert calls == [ir.ROUTER_MODEL, "anthropic/claude-opus-4.8"]


@pytest.mark.asyncio
async def test_classify_action_both_models_fail_falls_back(monkeypatch):
    """Both the router and main model failing degrades to a non-destructive answer."""
    from api.user.gpt.services.llm.client import llm

    async def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(llm, "ask", boom)
    out = await ir.classify_action("x", "ctx", [], main_model="anthropic/claude-opus-4.8")
    assert out == {"action": "answer", "file_key": None}
