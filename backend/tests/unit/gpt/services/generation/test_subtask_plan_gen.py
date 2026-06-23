"""Unit tests for subtask planning (generation.subtask_plan_gen)."""
import pytest

from api.user.gpt.services.generation import subtask_plan_gen as spg


def test_normalise_points_rescales_to_100():
    subs = [{"points": 10}, {"points": 10}, {"points": 10}]
    spg._normalise_points(subs)
    assert sum(s["points"] for s in subs) == 100


def test_normalise_points_noop_when_already_100():
    subs = [{"points": 40}, {"points": 60}]
    spg._normalise_points(subs)
    assert [s["points"] for s in subs] == [40, 60]


def test_normalise_points_empty_is_safe():
    spg._normalise_points([])


def test_cell_collapses_newlines_and_empty():
    assert spg._cell("a\nb") == "a b"
    assert spg._cell("") == "--"


def test_render_scoring_latex_contains_table_and_rows():
    subs = [
        {"group": "1", "points": 30, "constraints": "n <= 20", "depends_on": []},
        {"group": "2", "points": 70, "constraints": "n <= 1000", "depends_on": ["1"]},
    ]
    latex = spg.render_scoring_latex(subs)
    assert r"\begin{tabular}" in latex and r"\end{center}" in latex
    assert "$1$" in latex and "$30$" in latex and "n <= 20" in latex
    assert "тесты из условия" in latex


def test_render_scoring_latex_empty_returns_blank():
    assert spg.render_scoring_latex([]) == ""


@pytest.mark.asyncio
async def test_generate_normalises_and_filters(stub_llm):
    stub_llm(ask={"subtasks": [
        {"group": "1", "points": 50, "num_tests": 5, "partial_tag": "TL"},
        {"group": "2", "points": 50, "num_tests": "8", "partial_tag": "bogus"},
        "not-a-dict",
    ]})
    subs = await spg.generate({"name": "x"}, "model")
    assert len(subs) == 2
    assert sum(s["points"] for s in subs) == 100
    assert subs[0]["partial_tag"] == "TL"
    assert subs[1]["partial_tag"] == ""
    assert subs[1]["num_tests"] == 8


@pytest.mark.asyncio
async def test_generate_returns_empty_on_llm_error(monkeypatch):
    from api.user.gpt.services.llm.client import llm

    async def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(llm, "ask", boom)
    assert await spg.generate({}, "model") == []
