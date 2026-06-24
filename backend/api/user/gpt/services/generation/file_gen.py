"""Per-file generation: one distinct LLM call (and prompt) per technical file.

Replaces the old monolithic ``generate_technical_stuff`` mega-prompt. Each file
type is generated independently so the model focuses on a single artifact and so
an edit can regenerate exactly one file. ``generate_pack`` fans out over the file
types applicable to the problem type.
"""
import asyncio
import json
from typing import Dict

from api.user.gpt.services.files.file_registry import applicable_types, get_spec
from api.user.gpt.services.generation import test_plan_gen
from api.user.gpt.services.llm.client import llm, strip_code_fences
from api.user.gpt.services.llm.models import SCAFFOLD_MODEL
from api.user.gpt.services.prompts import (checker, generator, interactor,
                                           jury_answer, scorer, script,
                                           solution, validator)
from api.user.gpt.services.prompts.solution import build_system_prompt as _sol_prompt
from api.user.gpt.services.prompts import problem_type as problem_type_guide
from api.user.gpt.services.prompts.base import ASCII_CODE_RULE

_PACK_CONCURRENCY = 8


def _system_prompt(file_type: str, interactive: bool = False, problem_type=None) -> str:
    """Resolve the dedicated system prompt for a file type (+ ASCII-code rule)."""
    base = _base_system_prompt(file_type, interactive) + "\n" + ASCII_CODE_RULE
    if problem_type is not None:
        base = f"{problem_type_guide.guide(problem_type)}\n\n{base}"
    return base


def _base_system_prompt(file_type: str, interactive: bool = False) -> str:
    """Resolve the system prompt for a file type.

    Registered solution slots (solution_cpp/solution_py/wa_sol/tl_sol/re_sol/
    ml_sol) use their tag's solution prompt; anything unrecognised falls back to
    a generic MA solution prompt.
    """
    spec = get_spec(file_type)
    if file_type == "validator":
        return validator.SYSTEM_PROMPT
    if file_type == "generator":
        return generator.SYSTEM_PROMPT
    if file_type == "script":
        return script.SYSTEM_PROMPT
    if file_type == "interactor":
        return interactor.SYSTEM_PROMPT
    if file_type == "scorer":
        return scorer.SYSTEM_PROMPT
    if file_type == "jury_answer":
        return jury_answer.SYSTEM_PROMPT
    if file_type == "checker":
        return checker.INTERACTIVE_SYSTEM_PROMPT if interactive else checker.SYSTEM_PROMPT
    if spec and spec.category == "solution" and spec.tag:
        return _sol_prompt(spec.tag)
    return solution.build_system_prompt("MA")


def _user_prompt(statement: Dict) -> str:
    """Build the standard user prompt embedding the statement JSON."""
    return f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"


async def generate(file_type: str, statement: Dict, model: str, interactive: bool = False,
                   *, generator_code: str | None = None, plan_text: str | None = None,
                   problem_type=None) -> str:
    """Generate a single technical file from scratch.

    The generator and script both consume the pre-thought test plan (``plan_text``)
    so they share one set of opt parameters; the script also gets the generator's
    code so its parameter names match exactly (avoids testlib 'unused key').
    """
    if file_type == "script":
        user = script.build_user_prompt(statement, generator_code or "", plan_text or "")
    elif file_type == "generator":
        user = generator.build_user_prompt(statement, plan_text or "")
    else:
        user = _user_prompt(statement)
    messages = [
        {"role": "system", "content": _system_prompt(file_type, interactive, problem_type)},
        {"role": "user", "content": user},
    ]
    return strip_code_fences(await llm.ask_text(model, messages))


regenerate = generate


async def refine(
    file_type: str,
    current_code: str,
    feedback: str,
    statement: Dict,
    model: str,
    interactive: bool = False,
    problem_type=None,
) -> str:
    """Edit an existing file given user feedback, keeping its file-type prompt."""
    system = (
        _system_prompt(file_type, interactive, problem_type)
        + f"\nПользователь хочет внести правки в файл '{file_type}'. "
        "Верни обновлённую полную версию файла."
    )
    user = (
        f"{_user_prompt(statement)}\n\n"
        f"Текущий код ({file_type}):\n{current_code}\n\n"
        f"Правки пользователя: {feedback}"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return strip_code_fences(await llm.ask_text(model, messages))


def _grouping_note(subtasks: list[dict] | None) -> str:
    """Instruction appended to the test plan when the problem has subtasks.

    The script must emit tests grouped contiguously per subtask, in subtask order
    and with exactly the planned per-subtask test counts, so the build pipeline
    can map test index ranges onto Polygon test groups.
    """
    if not subtasks:
        return ""
    lines = [
        "",
        "ГРУППЫ ТЕСТОВ (подзадачи) — КРИТИЧЕСКИ ВАЖНО:",
        "Задача с подзадачами. Генерируй тесты строго блоками по подзадачам, "
        "в порядке возрастания номера подзадачи, и в КАЖДОЙ подзадаче ровно "
        "указанное число тестов. Тесты внутри блока должны удовлетворять "
        "ограничениям этой подзадачи (и всех, от которых она зависит).",
    ]
    for st in subtasks:
        lines.append(
            f"  - Подзадача {st.get('group')}: {st.get('num_tests', 5)} тест(ов); "
            f"ограничения: {st.get('constraints', '')}"
        )
    lines.append(
        "Суммарное число НЕ-семпловых тестов = сумма чисел выше. "
        "Порядок блоков менять нельзя."
    )
    return "\n".join(lines)


async def generate_pack(
    problem_type: str, statement: Dict, model: str,
    subtasks: list[dict] | None = None,
) -> Dict[str, str]:
    """Generate every file applicable to the problem type.

    Files are generated as concurrently as the data dependencies allow:
      - the test plan and every plan-independent file (validator, checker,
        solutions, …) start together;
      - the generator starts once the plan is ready;
      - the script starts once the generator is ready (it needs the generator's
        param names so testlib doesn't fail with 'unused key').
    So the only sequential critical path is plan → generator → script, with
    every other file overlapping it instead of running in separate waves.
    When ``subtasks`` is given, the script emits tests grouped by subtask.
    """
    interactive = str(problem_type) == "interactive" or getattr(problem_type, "value", None) == "interactive"
    types = applicable_types(problem_type)

    sem = asyncio.Semaphore(_PACK_CONCURRENCY)

    async def _one(ft: str, plan_text: str | None = None) -> tuple[str, str]:
        """Generate one file under the concurrency semaphore."""
        async with sem:
            return ft, await generate(ft, statement, model, interactive,
                                      plan_text=plan_text, problem_type=problem_type)

    # Plan + every file that doesn't depend on it start immediately, together.
    # The plan is internal scaffolding → cheap/fast model, not the main one.
    plan_task = asyncio.create_task(test_plan_gen.generate(statement, SCAFFOLD_MODEL))
    indep_tasks = [
        asyncio.create_task(_one(ft))
        for ft in types if ft not in ("script", "generator")
    ]

    plan_text = test_plan_gen.format_plan(await plan_task)

    # generator needs the plan; script needs the generator (+ plan).
    _, generator_code = await _one("generator", plan_text)
    pack: Dict[str, str] = {"generator": generator_code} if generator_code else {}

    script_task = None
    if "script" in types:
        script_task = asyncio.create_task(generate(
            "script", statement, model, interactive,
            generator_code=generator_code or "",
            plan_text=plan_text + _grouping_note(subtasks),
            problem_type=problem_type,
        ))

    for t in indep_tasks:
        ft, code = await t
        if code:
            pack[ft] = code

    if script_task is not None:
        script_code = await script_task
        if script_code:
            pack["script"] = script_code
    return pack
