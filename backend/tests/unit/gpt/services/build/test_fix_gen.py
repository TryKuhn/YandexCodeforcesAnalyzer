"""Unit tests for the code-fixing generator (services.build.fix_gen)."""
import json

import pytest

from api.user.gpt.services.build import fix_gen


@pytest.mark.asyncio
async def test_fix_returns_stripped_code(monkeypatch):
    async def fake_ask_text(model, messages):
        return "  fixed code here  \n"

    monkeypatch.setattr(fix_gen.llm, "ask_text", fake_ask_text)

    out = await fix_gen.fix(
        "checker", "broken", "some error", {"name": "P"}, "model-x"
    )
    assert out == "fixed code here"


@pytest.mark.asyncio
async def test_fix_includes_statement_and_broken_code_in_prompt(monkeypatch):
    captured = {}

    async def fake_ask_text(model, messages):
        captured["model"] = model
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(fix_gen.llm, "ask_text", fake_ask_text)

    statement = {"name": "Sum", "legend": "add"}
    await fix_gen.fix("checker", "BROKEN_CODE", "boom", statement, "model-x")

    assert captured["model"] == "model-x"
    user = captured["messages"][1]["content"]
    # statement is serialized into the user message
    assert json.dumps(statement, ensure_ascii=False) in user
    # the broken file itself is included
    assert "BROKEN_CODE" in user
    # system prompt mentions the component and error
    system = captured["messages"][0]["content"]
    assert "checker" in system and "boom" in system


@pytest.mark.asyncio
async def test_fix_includes_previous_errors_in_system_prompt(monkeypatch):
    captured = {}

    async def fake_ask_text(model, messages):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(fix_gen.llm, "ask_text", fake_ask_text)

    await fix_gen.fix(
        "generator", "code", "err", {}, "m",
        previous_errors=["prev-error-1", "prev-error-2"],
    )
    system = captured["messages"][0]["content"]
    assert "prev-error-1" in system and "prev-error-2" in system


@pytest.mark.asyncio
async def test_fix_includes_related_files_in_user_and_system(monkeypatch):
    captured = {}

    async def fake_ask_text(model, messages):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(fix_gen.llm, "ask_text", fake_ask_text)

    related = {"script": "SCRIPT_CONTENT"}
    await fix_gen.fix(
        "generator", "code", "err", {}, "m", related_files=related,
    )
    user = captured["messages"][1]["content"]
    system = captured["messages"][0]["content"]
    # related file content appears as read-only context in the user message
    assert "SCRIPT_CONTENT" in user
    assert "script" in user
    # related file note shows up in the system prompt
    assert "script" in system


@pytest.mark.asyncio
async def test_fix_skips_empty_related_file_content(monkeypatch):
    captured = {}

    async def fake_ask_text(model, messages):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(fix_gen.llm, "ask_text", fake_ask_text)

    await fix_gen.fix(
        "generator", "code", "err", {}, "m", related_files={"script": ""},
    )
    user = captured["messages"][1]["content"]
    # empty related content must not produce a "Related file" block
    assert "Related file 'script'" not in user
