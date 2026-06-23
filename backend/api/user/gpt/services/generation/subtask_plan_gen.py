"""Subtask (test-group) planning for points-based problems.

Produces a structured list of subtasks that is the single source of truth for:
  - the Scoring LaTeX table shown in the statement,
  - the per-subtask partial solutions,
  - the test grouping in the generation script,
  - the Polygon group/points configuration at build time.
"""
import json
from typing import Dict, List

from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.prompts.subtask_plan import SYSTEM_PROMPT

_VALID_TAGS = {"TL", "WA", "RJ", "ML", "RE"}


async def generate(statement: Dict, model: str) -> List[dict]:
    """Return a normalised list of subtask dicts (may be empty on failure).

    Each item: {group, points, constraints, strategy, num_tests, depends_on,
    partial_tag}.
    """
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
        return []

    raw = result.get("subtasks", []) if isinstance(result, dict) else []
    subtasks: List[dict] = []
    for i, st in enumerate(raw, start=1):
        if not isinstance(st, dict):
            continue
        try:
            points = int(float(st.get("points", 0)))
        except (ValueError, TypeError):
            points = 0
        try:
            num_tests = max(1, int(st.get("num_tests", 5)))
        except (ValueError, TypeError):
            num_tests = 5
        deps = [str(d) for d in (st.get("depends_on") or []) if str(d).strip()]
        tag = str(st.get("partial_tag", "") or "").upper()
        subtasks.append({
            "group": str(st.get("group", i)),
            "points": points,
            "constraints": str(st.get("constraints", "")),
            "strategy": str(st.get("strategy", "")),
            "num_tests": num_tests,
            "depends_on": deps,
            "partial_tag": tag if tag in _VALID_TAGS else "",
        })

    _normalise_points(subtasks)
    return subtasks


def _normalise_points(subtasks: List[dict]) -> None:
    """Make the points sum to exactly 100.

    Rescales proportionally, then absorbs any rounding remainder into the last
    subtask so the total lands on exactly 100.
    """
    if not subtasks:
        return
    total = sum(s["points"] for s in subtasks)
    if total == 100 or total <= 0:
        return
    acc = 0
    for s in subtasks[:-1]:
        s["points"] = max(1, round(s["points"] * 100 / total))
        acc += s["points"]
    subtasks[-1]["points"] = max(1, 100 - acc)


def _cell(text: str) -> str:
    """Escape a constraint string for a LaTeX table cell (keep $...$ math)."""
    return (text or "").replace("\n", " ").strip() or "--"


def render_scoring_latex(subtasks: List[dict]) -> str:
    """Render the subtask plan into the project's Scoring LaTeX table format."""
    if not subtasks:
        return ""
    rows = [
        r"\begin{center}",
        r"    \begin{tabular}{ | c | c | c | c | c | }",
        r"        \hline",
        r"        \textbf{\scriptsize{Подзадача}} &",
        r"        \textbf{\scriptsize{Баллы}} &",
        r"        \textbf{\scriptsize{Дополнительные ограничения}} &",
        r"        \textbf{\scriptsize{Необходимые подзадачи}} &",
        r"        \textbf{\scriptsize{Информация о проверке}} \\ \hline",
        r"        $0$ & -- & тесты из условия & -- & полная \\ \hline",
    ]
    for st in subtasks:
        deps = ", ".join(st["depends_on"]) if st["depends_on"] else "--"
        rows.append(
            f"        ${st['group']}$ & ${st['points']}$ & {_cell(st['constraints'])} "
            f"& {deps} & первая ошибка \\\\ \\hline"
        )
    rows.append(r"    \end{tabular}")
    rows.append(r"\end{center}")
    return "\n".join(rows)
