"""Prompt builder for solution files of a given tag (MA/OK/WA/TL/RE/ML/RJ)."""
from .base import INCORRECT_SOLUTION_RULES, NO_FENCES

TAG_DESCRIPTIONS = {
    "MA": "основное правильное решение (C++)",
    "OK": "альтернативное правильное решение (C++)",
    "WA": "решение с неверной логикой, которое выдаёт WA",
    "TL": "правильное, но медленное решение (O(n²) или хуже), которое выдаёт TL",
    "ML": "решение с избыточным расходом памяти, которое выдаёт ML",
    "RE": "решение, которое вызывает Runtime Error на некоторых тестах",
    "RJ": "отклоняемое решение (явно неверное)",
}

_INCORRECT_TAGS = {"WA", "TL", "ML", "RE", "RJ"}


def build_system_prompt(tag: str) -> str:
    """Build the system prompt for generating a solution of the given tag."""
    desc = TAG_DESCRIPTIONS.get(tag, f"решение с тегом {tag}")
    prompt = (
        "Ты — эксперт по разработке задач для Polygon. "
        f"Напиши {desc} для задачи."
    )
    if tag in _INCORRECT_TAGS:
        prompt += f"\n{INCORRECT_SOLUTION_RULES}"
    prompt += f"\n{NO_FENCES}"
    return prompt
