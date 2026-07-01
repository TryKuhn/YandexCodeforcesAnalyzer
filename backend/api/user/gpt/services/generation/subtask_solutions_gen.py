"""Generate one partial solution per subtask (except the final, full subtask).

Each partial solution correctly solves only its subtask and is expected to get a
non-OK verdict (TL/WA/…) on the full testset; that is exactly how Polygon shows
it scoring only the subtasks it actually passes. Returned items carry the custom
file_type key and the Polygon solution tag so the caller can register them in
``session.solution_meta`` and sync them as solutions.
"""
import asyncio
from typing import Dict, List, Tuple

from api.user.gpt.services.generation.solution_skip import parse_skip
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
) -> Tuple[List[dict], Dict[str, str]]:
    """Return ``(partials, skipped)`` for non-final subtasks.

    ``partials`` = [{file_type, code, tag, name, group}]; ``skipped`` maps a
    subtask label -> the reason its partial solution was declined (the model
    couldn't guarantee the expected verdict with a genuine algorithm). The last
    subtask is the full problem — already covered by the main solution (MA) — so
    no partial is generated for it.
    """
    if len(subtasks) < 2:
        return [], {}

    targets = [st for st in subtasks[:-1] if st.get("partial_tag")]
    if not targets:
        return [], {}

    sem = asyncio.Semaphore(_CONCURRENCY)
    guide = problem_type_guide.guide(problem_type) if problem_type is not None else ""

    async def _one(st: dict) -> dict | None:
        """Generate one partial solution for a subtask (or a skip/None marker)."""
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
            reason = parse_skip(code)
            if reason is not None:
                return {"skip": True, "group": st["group"],
                        "tag": st["partial_tag"], "reason": reason}
            return {
                "file_type": f"sol_sub{st['group']}",
                "code": code,
                "tag": st["partial_tag"],
                "name": f"sub{st['group']}",
                "group": st["group"],
            }

    results = await asyncio.gather(*[_one(st) for st in targets])
    partials = [r for r in results if r and not r.get("skip")]
    skipped = {
        f"подзадача {r['group']} ({r['tag']})": r["reason"]
        for r in results if r and r.get("skip")
    }
    return partials, skipped
