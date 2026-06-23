"""Generate one partial solution per subtask (except the final, full subtask).

Each partial solution correctly solves only its subtask and is expected to get a
non-OK verdict (TL/WA/…) on the full testset; that is exactly how Polygon shows
it scoring only the subtasks it actually passes. Returned items carry the custom
file_type key and the Polygon solution tag so the caller can register them in
``session.solution_meta`` and sync them as solutions.
"""
import asyncio
from typing import Dict, List

from api.user.gpt.services.llm.client import llm, strip_code_fences
from api.user.gpt.services.prompts import problem_type as problem_type_guide
from api.user.gpt.services.prompts.subtask_solution import build_system_prompt

_CONCURRENCY = 3


def _user_prompt(statement: Dict) -> str:
    """Build the user prompt embedding the statement JSON."""
    import json
    return f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"


async def generate(
    statement: Dict, model: str, subtasks: List[dict], problem_type=None
) -> List[dict]:
    """Return [{file_type, code, tag, name, group}] for non-final subtasks.

    The last subtask is the full problem — it is already covered by the main
    solution (tag MA), so no partial solution is generated for it.
    """
    if len(subtasks) < 2:
        return []

    targets = [st for st in subtasks[:-1] if st.get("partial_tag")]
    if not targets:
        return []

    sem = asyncio.Semaphore(_CONCURRENCY)
    guide = problem_type_guide.guide(problem_type) if problem_type is not None else ""

    async def _one(st: dict) -> dict | None:
        """Generate one partial solution for a single subtask (or None if empty)."""
        async with sem:
            system = build_system_prompt(
                st["group"], st.get("constraints", ""),
                st.get("strategy", ""), st["partial_tag"],
            )
            if guide:
                system = f"{guide}\n\n{system}"
            code = strip_code_fences(await llm.ask_text(
                model,
                [{"role": "system", "content": system},
                 {"role": "user", "content": _user_prompt(statement)}],
            ))
            if not code.strip():
                return None
            return {
                "file_type": f"sol_sub{st['group']}",
                "code": code,
                "tag": st["partial_tag"],
                "name": f"sub{st['group']}",
                "group": st["group"],
            }

    results = await asyncio.gather(*[_one(st) for st in targets])
    return [r for r in results if r]
