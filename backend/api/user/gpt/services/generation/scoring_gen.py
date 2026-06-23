"""Scoring-section generation.

Regular/interactive problems get a subtask LaTeX table; output-only problems get
a description of the scorer's grading rules (objective + partial points).
"""
import json
from typing import Dict

from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.prompts.output_scoring import \
    SYSTEM_PROMPT as OUTPUT_SYSTEM_PROMPT
from api.user.gpt.services.prompts.scoring import SYSTEM_PROMPT


def _user_prompt(statement: Dict) -> str:
    """Build the user prompt embedding the statement JSON."""
    return f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"


async def generate(
    statement: Dict,
    model: str,
    enable_groups: bool,
    enable_points: bool,
    problem_type: str | None = None,
) -> str:
    """Generate the Scoring section text.

    Output-only problems get the scorer grading-rules description; otherwise a
    subtask LaTeX table is produced when groups or points are enabled (else "").
    """
    if str(problem_type) == "output_only":
        messages = [
            {"role": "system", "content": OUTPUT_SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(statement)},
        ]
        return await llm.ask_text(model, messages)

    if not enable_groups and not enable_points:
        return ""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _user_prompt(statement)},
    ]
    return await llm.ask_text(model, messages)
