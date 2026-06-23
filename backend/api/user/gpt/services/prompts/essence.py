"""Prompt for detecting whether a statement edit changed the problem's essence.

Used after an AI statement edit to decide whether dependent files (validator,
generator, checker, solutions, ...) must be regenerated.
"""

SYSTEM_PROMPT = (
    "Ты анализируешь правку условия задачи по спортивному программированию. "
    "Определи, изменилась ли СУТЬ задачи, то есть то, что влияет на технические файлы: "
    "ограничения (n, пределы значений), формат ввода/вывода, сама постановка/алгоритм задачи, "
    "структура подзадач/баллов. Косметические правки (опечатки, формулировки, оформление, "
    "имена переменных в тексте) сутью НЕ являются.\n"
    "Верни ТОЛЬКО JSON: "
    '{"essence_changed": true|false, '
    '"dependents": ["validator"|"generator"|"checker"|"script"|"solution_cpp"|'
    '"solution_py"|"wa_sol"|"tl_sol"|"re_sol"|"ml_sol"|"interactor"|"scorer"], '
    '"reason": "кратко"}. '
    "В dependents перечисли ТОЛЬКО те типы файлов, которые реально нужно перегенерировать "
    "из-за этой правки (пустой список, если essence_changed=false)."
)


def build_user_prompt(old_statement: str, new_statement: str) -> str:
    """Build the user prompt presenting the old and new statement for comparison."""
    return (
        f"СТАРОЕ условие:\n{old_statement}\n\n"
        f"НОВОЕ условие:\n{new_statement}"
    )
