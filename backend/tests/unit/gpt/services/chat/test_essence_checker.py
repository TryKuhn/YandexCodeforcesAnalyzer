"""Unit tests for the essence checker (services.chat.essence_checker)."""
import pytest

from api.user.gpt.services.chat import essence_checker as ec


@pytest.mark.asyncio
async def test_check_essence_changed(stub_llm):
    stub_llm(ask={"essence_changed": True,
                  "dependents": ["validator", "checker"],
                  "reason": "constraints changed"})
    out = await ec.check({"name": "old"}, {"name": "new"})
    assert out == {
        "essence_changed": True,
        "dependents": ["validator", "checker"],
        "reason": "constraints changed",
    }


@pytest.mark.asyncio
async def test_check_cosmetic_edit(stub_llm):
    stub_llm(ask={"essence_changed": False, "dependents": [], "reason": "typo"})
    out = await ec.check({}, {})
    assert out["essence_changed"] is False
    assert out["dependents"] == []
    assert out["reason"] == "typo"


@pytest.mark.asyncio
async def test_check_normalises_missing_fields(stub_llm):
    stub_llm(ask={})  # nothing returned
    out = await ec.check({}, {})
    assert out == {"essence_changed": False, "dependents": [], "reason": ""}


@pytest.mark.asyncio
async def test_check_filters_falsy_dependents_and_stringifies(stub_llm):
    stub_llm(ask={"essence_changed": 1, "dependents": ["validator", "", None, 5],
                  "reason": 42})
    out = await ec.check({}, {})
    assert out["essence_changed"] is True
    assert out["dependents"] == ["validator", "5"]
    assert out["reason"] == "42"


@pytest.mark.asyncio
async def test_check_llm_error_returns_safe_default(monkeypatch):
    from api.user.gpt.services.llm.client import llm

    async def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(llm, "ask", boom)
    out = await ec.check({}, {})
    assert out == {"essence_changed": False, "dependents": [], "reason": ""}
