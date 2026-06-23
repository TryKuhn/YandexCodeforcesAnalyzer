"""Test-plan generation: decide generator params (opt) + seed before coding.

The plan is consumed by both the generator and the script so they share one set
of parameter names (consistency) and agree on whether a seed is needed.
"""
import json
from typing import Dict

from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.prompts.test_plan import SYSTEM_PROMPT


async def generate(statement: Dict, model: str) -> dict:
    """Return {"params": [{name,type,description}], "use_seed": bool, "strategy": str}."""
    try:
        result = await llm.ask(
            model,
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",
                 "content": f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"},
            ],
            json_mode=True,
        )
    except Exception:
        return {"params": [], "use_seed": False, "strategy": ""}

    params = []
    for p in result.get("params", []):
        if isinstance(p, dict) and p.get("name"):
            params.append({
                "name": str(p["name"]),
                "type": str(p.get("type", "int")),
                "description": str(p.get("description", "")),
            })
    return {
        "params": params,
        "use_seed": bool(result.get("use_seed", False)),
        "strategy": str(result.get("strategy", "")),
    }


def format_plan(plan: dict) -> str:
    """Human-readable plan block for generator/script prompts."""
    if not plan or not plan.get("params"):
        return ""
    lines = ["План тестов (продуман заранее):"]
    lines.append("Параметры генератора (opt), которые нужно реализовать/использовать:")
    for p in plan["params"]:
        lines.append(f"  - {p['name']} ({p['type']}): {p['description']}")
    if plan.get("use_seed"):
        lines.append("seed НУЖЕН: генератор читает opt seed и использует его для rnd, "
                     "скрипт варьирует seed, чтобы тесты с одинаковыми параметрами различались.")
    if plan.get("strategy"):
        lines.append(f"Стратегия тестов: {plan['strategy']}")
    return "\n".join(lines)
