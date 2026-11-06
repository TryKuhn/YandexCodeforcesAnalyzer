"""Problem-type guidance: what a regular / interactive / output-only problem is
made of and how each kind is handled in Polygon.

The block goes into the problem materials (``sync.dossier``), so every model
call that sees the problem -- router, answers, edits, generation steps, build
repairs -- works with the right type. Pure data, no imports: both the prompts
and the dossier use it.
"""
from __future__ import annotations

REGULAR = "regular"
INTERACTIVE = "interactive"
OUTPUT_ONLY = "output_only"

# max points of one output-only test; the scorer awards quitp(<0..this>)
OUTPUT_ONLY_TEST_POINTS = 10

_GUIDES = {
    REGULAR: (
        "ТИП ЗАДАЧИ: ОБЫЧНАЯ (regular). Участник читает вход из stdin (или входного файла) и печатает ответ в "
        "stdout. Состав: условие (legend/input/output/notes), валидатор, генераторы + FreeMarker-скрипт тестов, "
        "чекер (стандартный или свой), главное решение (MA) и решения с другими тегами для проверки тестов. "
        "Интерактор НЕ нужен, раздела «Взаимодействие» в условии быть не должно."
    ),
    INTERACTIVE: (
        "ТИП ЗАДАЧИ: ИНТЕРАКТИВНАЯ (interactive). Решение участника общается с интерактором через stdin/stdout "
        "в режиме запрос-ответ. Как это устроено в Polygon:\n"
        "- входной файл теста (то, что генерирует генератор и проверяет валидатор) -- это СКРЫТЫЕ данные для "
        "интерактора (загаданное число, массив, параметры адаптивности); участник его не видит;\n"
        "- интерактор (interactor.cpp, testlib): registerInteraction(argc, argv); читает тест из inf, общается с "
        "участником (запросы читает из ouf, ответы пишет в cout с endl/fflush), проверяет корректность запросов и "
        "лимит их числа, при нарушении -- quitf(_wa, ...) / quitf(_pe, ...); в конце пишет в tout итог (например, "
        "найденный ответ участника или число запросов) и завершается quitf(_ok, ...);\n"
        "- чекер получает вывод интерактора (tout) как ouf и такой же вывод для главного решения как ans; обычно "
        "достаточно стандартного std::wcmp.cpp или простого своего чекера;\n"
        "- главное решение (MA) и другие решения печатают запросы с flush после каждого вывода "
        "(cout << ... << endl или fflush(stdout)) и читают ответы из stdin;\n"
        "- в условии ОБЯЗАТЕЛЕН раздел interaction («Протокол взаимодействия»): формат запросов и ответов, лимит "
        "числа запросов, как сообщить ответ, требование flush; в input описывается, что получает программа в "
        "начале (если что-то получает), в output -- формат финального ответа; пример диалога -- в notes;\n"
        "- примеры (тесты из условия) -- это входные файлы интерактора."
    ),
    OUTPUT_ONLY: (
        "ТИП ЗАДАЧИ: OUTPUT-ONLY (вывод-только). Участник НЕ сдаёт программу: он получает все входные файлы и "
        "сдаёт ответ на каждый тест. Как это устроено в Polygon:\n"
        "- тесты -- входные файлы (генераторы + скрипт, как обычно), валидатор проверяет их;\n"
        "- чекер -- это СКОРЕР (testlib, registerTestlibCmd): читает тест из inf, ответ жюри из ans, ответ "
        "участника из ouf; структурно проверяет ответ участника (ouf.readInt/readLong с границами, "
        "ouf.quitif(..., _wa, ...)) и начисляет ЧАСТИЧНЫЕ баллы через quitp(<double>, ...) -- абсолютные баллы "
        f"теста от 0 до {OUTPUT_ONLY_TEST_POINTS} (полный балл за ответ не хуже жюри, иначе пропорциональная доля); "
        "некорректный ответ -- quitf(_wa, ...);\n"
        "- главное решение (MA) -- эталонный решатель жюри: его вывод становится ответом жюри (*.a);\n"
        f"- баллы в задаче ВСЕГДА включены, за каждый тест до {OUTPUT_ONLY_TEST_POINTS} баллов, групп нет;\n"
        "- в условии ОБЯЗАТЕЛЕН раздел scoring («Система оценки»): что сдаёт участник, целевая функция, формула "
        "баллов за тест (та же, что в скорере), итог -- сумма по тестам; переборного решения не нужно;\n"
        "- интерактор не нужен."
    ),
}

TYPE_LABELS = {REGULAR: "обычная", INTERACTIVE: "интерактивная", OUTPUT_ONLY: "output-only"}


def normalize_type(problem_type: str | None) -> str:
    value = str(problem_type or REGULAR)
    return value if value in _GUIDES else REGULAR


def type_guide(problem_type: str | None) -> str:
    """The guidance block for ``problem_type`` (unknown -> regular)."""
    return _GUIDES[normalize_type(problem_type)]
