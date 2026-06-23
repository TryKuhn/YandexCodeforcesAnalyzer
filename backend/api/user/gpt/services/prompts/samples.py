"""Prompt for generating small sample tests for the statement."""


def build_system_prompt(count: int) -> str:
    """Build the system prompt asking the model for ``count`` sample tests as JSON."""
    return (
        "Ты — эксперт по задачам спортивного программирования. "
        "Создай небольшие демонстрационные примеры (сэмплы) для задачи. "
        f"Нужно {count} примера. Каждый пример должен быть небольшим (буквально 1–5 строк ввода), "
        "понятным, покрывающим разные случаи: базовый, граничный, неочевидный. "
        "Вычисли правильный ответ для каждого теста. "
        'Выведи JSON: {"examples": [{"input": "...", "output": "..."}, ...]}'
    )
