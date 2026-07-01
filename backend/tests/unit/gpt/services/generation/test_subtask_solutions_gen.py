"""Unit tests for per-subtask partial-solution generation (subtask_solutions_gen)."""
import pytest

from api.user.gpt.services.generation import subtask_solutions_gen as ssg
from api.user.gpt.services.llm.client import llm


def _sub(group, partial_tag=None, **extra):
    s = {"group": group, "constraints": f"n<={group}", "strategy": "s"}
    if partial_tag is not None:
        s["partial_tag"] = partial_tag
    s.update(extra)
    return s


@pytest.mark.asyncio
async def test_generate_skips_when_fewer_than_two_subtasks(stub_llm):
    stub_llm(ask_text="code")
    assert await ssg.generate({}, "m", []) == ([], {})
    assert await ssg.generate({}, "m", [_sub("1", "TL")]) == ([], {})


@pytest.mark.asyncio
async def test_generate_returns_empty_when_no_partial_tags(stub_llm):
    stub_llm(ask_text="code")
    # Last subtask is dropped (full problem); remaining have no partial_tag.
    subs = [_sub("1"), _sub("2"), _sub("3")]
    assert await ssg.generate({}, "m", subs) == ([], {})


@pytest.mark.asyncio
async def test_generate_builds_items_for_non_final_tagged(stub_llm):
    stub_llm(ask_text="solution code")
    subs = [_sub("1", "TL"), _sub("2", "WA"), _sub("3", "MA")]
    out, skipped = await ssg.generate({"name": "x"}, "m", subs)
    assert skipped == {}
    # Only subtasks 1 and 2 (last subtask is excluded).
    assert len(out) == 2
    by_group = {r["group"]: r for r in out}
    assert by_group["1"] == {
        "file_type": "sol_sub1",
        "code": "solution code",
        "tag": "TL",
        "name": "sub1",
        "group": "1",
    }
    assert by_group["2"]["tag"] == "WA"


@pytest.mark.asyncio
async def test_generate_filters_out_empty_code(monkeypatch):
    async def fake_ask_text(model, messages):
        # Return empty for group 1, real code for group 2.
        if "n<=1" in messages[0]["content"]:
            return "   "
        return "real code"

    monkeypatch.setattr(llm, "ask_text", fake_ask_text)
    subs = [_sub("1", "TL"), _sub("2", "WA"), _sub("3", "MA")]
    out, _ = await ssg.generate({}, "m", subs)
    groups = {r["group"] for r in out}
    assert groups == {"2"}


@pytest.mark.asyncio
async def test_generate_strips_code_fences(stub_llm):
    stub_llm(ask_text="```cpp\nint main(){}\n```")
    subs = [_sub("1", "TL"), _sub("2", "MA")]
    out, _ = await ssg.generate({}, "m", subs)
    assert out[0]["code"] == "int main(){}"


@pytest.mark.asyncio
async def test_generate_only_targets_subtasks_with_partial_tag(stub_llm):
    stub_llm(ask_text="code")
    # group 1 has no partial_tag, group 2 does; group 3 is final.
    subs = [_sub("1"), _sub("2", "WA"), _sub("3", "MA")]
    out, _ = await ssg.generate({}, "m", subs)
    assert [r["group"] for r in out] == ["2"]


@pytest.mark.asyncio
async def test_generate_skips_when_model_declines(stub_llm):
    # The model returns a SKIP marker → that subtask's partial is omitted and its
    # reason is reported in the skipped map, not created as a bogus file.
    stub_llm(ask_text="SKIP: нельзя гарантировать TL честным алгоритмом")
    subs = [_sub("1", "TL"), _sub("2", "MA")]
    out, skipped = await ssg.generate({}, "m", subs)
    assert out == []
    assert "подзадача 1 (TL)" in skipped
