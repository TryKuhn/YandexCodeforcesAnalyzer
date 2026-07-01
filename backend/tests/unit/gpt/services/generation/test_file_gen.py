"""Unit tests for per-file generation (generation.file_gen)."""
import pytest

from api.user.gpt.services.generation import file_gen as fg
from api.user.gpt.services.llm.client import llm
from models.task.session import ProblemType


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------
def test_grouping_note_empty_when_no_subtasks():
    assert fg._grouping_note(None) == ""
    assert fg._grouping_note([]) == ""


def test_grouping_note_lists_each_subtask():
    subs = [
        {"group": "1", "num_tests": 4, "constraints": "n<=10"},
        {"group": "2", "num_tests": 6, "constraints": "n<=100"},
    ]
    note = fg._grouping_note(subs)
    assert "ГРУППЫ ТЕСТОВ" in note
    assert "Подзадача 1: 4 тест(ов); ограничения: n<=10" in note
    assert "Подзадача 2: 6 тест(ов); ограничения: n<=100" in note


def test_grouping_note_defaults_num_tests():
    note = fg._grouping_note([{"group": "1"}])
    assert "Подзадача 1: 5 тест(ов)" in note


def test_user_prompt_carries_statement_json():
    out = fg._user_prompt({"name": "P"})
    assert "Условие задачи" in out
    assert '"name": "P"' in out


def test_base_system_prompt_dispatch_by_type():
    from api.user.gpt.services.prompts import validator, generator, checker
    assert fg._base_system_prompt("validator") == validator.SYSTEM_PROMPT
    assert fg._base_system_prompt("generator") == generator.SYSTEM_PROMPT
    assert fg._base_system_prompt("checker", interactive=False) == checker.SYSTEM_PROMPT
    assert fg._base_system_prompt("checker", interactive=True) == checker.INTERACTIVE_SYSTEM_PROMPT


def test_base_system_prompt_solution_uses_tag():
    # solution_cpp -> tag MA via build_system_prompt
    from api.user.gpt.services.prompts.solution import build_system_prompt
    assert fg._base_system_prompt("solution_cpp") == build_system_prompt("MA")


def test_system_prompt_appends_ascii_rule():
    from api.user.gpt.services.prompts.base import ASCII_CODE_RULE
    out = fg._system_prompt("validator")
    assert ASCII_CODE_RULE in out


def test_system_prompt_prepends_problem_type_guide():
    out = fg._system_prompt("validator", problem_type=ProblemType.INTERACTIVE)
    assert "ИНТЕРАКТИВНАЯ" in out


# --------------------------------------------------------------------------
# generate
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_returns_stripped_text(stub_llm):
    stub_llm(ask_text="```cpp\ncode\n```")
    out = await fg.generate("validator", {"name": "x"}, "model")
    assert out == "code"


@pytest.mark.asyncio
async def test_generate_script_uses_script_prompt(monkeypatch):
    captured = {}

    async def fake_ask_text(model, messages):
        captured["messages"] = messages
        return "script code"

    monkeypatch.setattr(llm, "ask_text", fake_ask_text)
    out = await fg.generate(
        "script", {"name": "x"}, "model",
        generator_code="gen code", plan_text="PLAN",
    )
    assert out == "script code"
    # script user prompt should embed the plan text / generator code.
    user = captured["messages"][1]["content"]
    assert "PLAN" in user or "gen code" in user


@pytest.mark.asyncio
async def test_generate_generator_uses_plan_text(monkeypatch):
    captured = {}

    async def fake_ask_text(model, messages):
        captured["messages"] = messages
        return "gen"

    monkeypatch.setattr(llm, "ask_text", fake_ask_text)
    await fg.generate("generator", {"name": "x"}, "model", plan_text="MYPLAN")
    assert "MYPLAN" in captured["messages"][1]["content"]


@pytest.mark.asyncio
async def test_generate_default_file_uses_statement_user_prompt(monkeypatch):
    captured = {}

    async def fake_ask_text(model, messages):
        captured["messages"] = messages
        return "code"

    monkeypatch.setattr(llm, "ask_text", fake_ask_text)
    await fg.generate("solution_cpp", {"name": "P"}, "model")
    assert "Условие задачи" in captured["messages"][1]["content"]


# --------------------------------------------------------------------------
# refine
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_refine_includes_current_code_and_feedback(monkeypatch):
    captured = {}

    async def fake_ask_text(model, messages):
        captured["messages"] = messages
        return "```\nnew code\n```"

    monkeypatch.setattr(llm, "ask_text", fake_ask_text)
    out = await fg.refine("validator", "old code", "make it stricter", {"name": "x"}, "model")
    assert out == "new code"
    user = captured["messages"][1]["content"]
    assert "old code" in user
    assert "make it stricter" in user
    # system prompt instructs to return the full updated file.
    assert "обновлённую полную версию" in captured["messages"][0]["content"]


# --------------------------------------------------------------------------
# generate_pack
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generate_pack_regular(monkeypatch):
    # Stub test_plan_gen.generate so no real plan LLM call happens.
    async def fake_plan(statement, model):
        return {"params": [], "use_seed": False, "strategy": ""}

    monkeypatch.setattr(
        "api.user.gpt.services.generation.file_gen.test_plan_gen.generate", fake_plan
    )

    calls = []

    async def fake_generate(file_type, statement, model, interactive=False, *,
                            generator_code=None, plan_text=None, problem_type=None):
        calls.append(file_type)
        return f"// {file_type}"

    monkeypatch.setattr(fg, "generate", fake_generate)

    pack, skipped = await fg.generate_pack("regular", {"name": "x"}, "model")
    assert skipped == {}
    expected = set(__import__(
        "api.user.gpt.services.files.file_registry",
        fromlist=["applicable_types"],
    ).applicable_types("regular"))
    assert set(pack.keys()) == expected
    assert "script" in pack
    # script generated, and so was every other applicable type.
    assert set(calls) == expected


@pytest.mark.asyncio
async def test_generate_pack_drops_empty_results(monkeypatch):
    async def fake_plan(statement, model):
        return {"params": [], "use_seed": False, "strategy": ""}

    monkeypatch.setattr(
        "api.user.gpt.services.generation.file_gen.test_plan_gen.generate", fake_plan
    )

    async def fake_generate(file_type, statement, model, interactive=False, *,
                            generator_code=None, plan_text=None, problem_type=None):
        # validator returns empty -> should be dropped from the pack.
        if file_type == "validator":
            return ""
        return f"// {file_type}"

    monkeypatch.setattr(fg, "generate", fake_generate)
    pack, _ = await fg.generate_pack("regular", {"name": "x"}, "model")
    assert "validator" not in pack
    assert "generator" in pack


@pytest.mark.asyncio
async def test_generate_pack_interactive_includes_interactor(monkeypatch):
    async def fake_plan(statement, model):
        return {"params": [], "use_seed": False, "strategy": ""}

    monkeypatch.setattr(
        "api.user.gpt.services.generation.file_gen.test_plan_gen.generate", fake_plan
    )

    seen_interactive = {}

    async def fake_generate(file_type, statement, model, interactive=False, *,
                            generator_code=None, plan_text=None, problem_type=None):
        seen_interactive[file_type] = interactive
        return f"// {file_type}"

    monkeypatch.setattr(fg, "generate", fake_generate)
    pack, _ = await fg.generate_pack("interactive", {"name": "x"}, "model")
    assert "interactor" in pack
    # interactive flag propagated to generate().
    assert all(v is True for v in seen_interactive.values())


@pytest.mark.asyncio
async def test_generate_pack_passes_grouping_note_to_script(monkeypatch):
    async def fake_plan(statement, model):
        return {"params": [{"name": "n", "type": "int", "description": "d"}],
                "use_seed": False, "strategy": ""}

    monkeypatch.setattr(
        "api.user.gpt.services.generation.file_gen.test_plan_gen.generate", fake_plan
    )

    script_plan = {}

    async def fake_generate(file_type, statement, model, interactive=False, *,
                            generator_code=None, plan_text=None, problem_type=None):
        if file_type == "script":
            script_plan["plan_text"] = plan_text
        return f"// {file_type}"

    monkeypatch.setattr(fg, "generate", fake_generate)
    subtasks = [{"group": "1", "num_tests": 3, "constraints": "n<=5"}]
    await fg.generate_pack("regular", {"name": "x"}, "model", subtasks=subtasks)
    assert "ГРУППЫ ТЕСТОВ" in script_plan["plan_text"]
