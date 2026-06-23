"""Unit tests for checker+validator generation (generation.checker_validator_gen)."""
import pytest

from api.user.gpt.services.generation import checker_validator_gen as cvg
from api.user.gpt.services.llm.client import llm
from api.user.polygon.archive.parser import Statement


def _statement() -> Statement:
    return Statement(
        letter="A",
        title="Sum",
        legend=["Compute the sum."],
        input_format=["Two integers a and b."],
        output_format=["Their sum."],
        examples=[("1 2", "3")],
    )


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------
def test_statement_summary_includes_sections():
    text = cvg._statement_summary(_statement())
    assert "Название: Sum" in text
    assert "Легенда" in text
    assert "Формат входных данных" in text
    assert "Пример 1" in text


def test_statement_summary_truncates():
    st = _statement()
    st.legend = ["x" * 10000]
    text = cvg._statement_summary(st, max_len=100)
    assert len(text) == 100


def test_statement_summary_falls_back_to_letter():
    st = Statement(letter="B", title="")
    text = cvg._statement_summary(st)
    assert "Название: B" in text


def test_build_prompt_lists_standard_checkers():
    prompt = cvg._build_prompt(_statement())
    assert "std::wcmp.cpp" in prompt
    assert "Верни строго JSON" in prompt


# --------------------------------------------------------------------------
# generate_checker_validator
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_returns_result(monkeypatch):
    async def fake_ask(model, messages, json_mode=True):
        return {
            "checker": {"type": "standard", "name": "std::wcmp.cpp"},
            "validator": {"code": "int main(){}"},
            "comment": "wcmp fits",
        }

    monkeypatch.setattr(llm, "ask", fake_ask)
    result = await cvg.generate_checker_validator(_statement(), "model")
    assert result["checker"]["name"] == "std::wcmp.cpp"
    assert result["comment"] == "wcmp fits"


@pytest.mark.asyncio
async def test_generate_normalises_angle_bracket_includes(monkeypatch):
    async def fake_ask(model, messages, json_mode=True):
        return {
            "checker": {"type": "custom", "code": '#include <testlib.h>\nint main(){}'},
            "validator": {"code": '#include < testlib.h >\nint main(){}'},
        }

    monkeypatch.setattr(llm, "ask", fake_ask)
    result = await cvg.generate_checker_validator(_statement(), "model")
    assert '#include "testlib.h"' in result["checker"]["code"]
    assert "<testlib.h>" not in result["checker"]["code"]
    assert '#include "testlib.h"' in result["validator"]["code"]


@pytest.mark.asyncio
async def test_generate_raises_when_missing_keys(monkeypatch):
    async def fake_ask(model, messages, json_mode=True):
        return {"checker": {"type": "standard", "name": "std::wcmp.cpp"}}

    monkeypatch.setattr(llm, "ask", fake_ask)
    with pytest.raises(ValueError):
        await cvg.generate_checker_validator(_statement(), "model")


@pytest.mark.asyncio
async def test_generate_handles_non_dict_parts(monkeypatch):
    # checker/validator present but not dicts -> no crash, returned as-is.
    async def fake_ask(model, messages, json_mode=True):
        return {"checker": "std::wcmp.cpp", "validator": {"code": ""}}

    monkeypatch.setattr(llm, "ask", fake_ask)
    result = await cvg.generate_checker_validator(_statement(), "model")
    assert result["checker"] == "std::wcmp.cpp"
