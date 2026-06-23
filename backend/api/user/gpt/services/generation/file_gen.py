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
from api.user.gpt.services.prompts import (checker, generator, interactor,
                                           jury_answer, scorer, script,
                                           solution, validator)
from api.user.gpt.services.prompts.solution import build_system_prompt as _sol_prompt
from api.user.gpt.services.prompts import problem_type as problem_type_guide

_PACK_CONCURRENCY = 4


from api.user.gpt.services.prompts.base import ASCII_CODE_RULE


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

    Everything except the script is generated concurrently; the script is then
    generated last with the generator's code in context so its parameter names
    match exactly (otherwise testlib fails with 'unused key'). When ``subtasks``
    is given, the script is told to emit tests grouped by subtask.
    """
    interactive = str(problem_type) == "interactive" or getattr(problem_type, "value", None) == "interactive"
    types = applicable_types(problem_type)
    non_script = [ft for ft in types if ft != "script"]

    plan = await test_plan_gen.generate(statement, model)
    plan_text = test_plan_gen.format_plan(plan)
    script_plan_text = plan_text + _grouping_note(subtasks)

    sem = asyncio.Semaphore(_PACK_CONCURRENCY)

    async def _one(ft: str) -> tuple[str, str]:
        """Generate one non-script file under the concurrency semaphore."""
        async with sem:
            pt = plan_text if ft == "generator" else None
            return ft, await generate(ft, statement, model, interactive,
                                      plan_text=pt, problem_type=problem_type)

    results = await asyncio.gather(*[_one(ft) for ft in non_script])
    pack = {ft: code for ft, code in results if code}

    if "script" in types:
        script_code = await generate(
            "script", statement, model, interactive,
            generator_code=pack.get("generator", ""), plan_text=script_plan_text,
            problem_type=problem_type,
        )
        if script_code:
            pack["script"] = script_code
    return pack
