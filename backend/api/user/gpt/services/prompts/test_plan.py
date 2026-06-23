"""Prompt for planning the test set BEFORE writing the generator and script.

Thinking about the tests first yields a single set of generator parameters
(opt names) that both the generator and the Freemarker script then follow — so
they stay consistent (no testlib 'unused key'). It also decides whether a `seed`
parameter is needed (when several DIFFERENT random tests must share the same
control parameters, seed is what makes them differ).
"""

SYSTEM_PROMPT = (
    "Ты — эксперт по тестированию задач спортивного программирования. "
    "ДО написания генератора продумай набор тестов для задачи и определи:\n"
    "1) Какие параметры (opt) нужны генератору для управления тестами: размер входа, "
    "границы значений, структурные особенности (отсортированность, тип графа и т.п.). "
    "Дай короткие латинские имена (n, m, maxVal, minVal, type, ...).\n"
    "2) Нужен ли параметр seed. seed НУЖЕН, если для покрытия требуется несколько "
    "РАЗНЫХ случайных тестов с ОДИНАКОВЫМИ управляющими параметрами — именно seed "
    "делает такие тесты различными (нельзя генерировать одинаковые тесты).\n"
    "3) Стратегию тестов: минимальные (n=1), граничные, максимальные/стресс (n=макс), "
    "специальные случаи из условия.\n"
    "Верни ТОЛЬКО JSON: "
    '{"params": [{"name": "...", "type": "int|long|string", "description": "..."}], '
    '"use_seed": true|false, "strategy": "краткое описание групп тестов"}. '
    "Если use_seed=true, ОБЯЗАТЕЛЬНО включи параметр seed в список params."
)
