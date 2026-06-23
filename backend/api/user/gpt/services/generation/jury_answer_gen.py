"""Jury reference-solver generation (output-only problems).

Thin wrapper over file_gen: the jury answer is produced by running this MA
solution during package build (Polygon has no upload-answer API).
"""
from typing import Dict

from api.user.gpt.services.generation import file_gen


async def generate(statement: Dict, model: str) -> str:
    """Generate the MA jury reference solver for an output-only problem."""
    return await file_gen.generate("jury_answer", statement, model)
