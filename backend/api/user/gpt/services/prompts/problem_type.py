"""Problem-type guidance block, injected into every AI request.

Tells the model which kind of problem is being authored (regular / interactive /
output-only) and how each type must be handled, so generation and answers always
respect the chosen type.
"""
from models.task.session import ProblemType

_REGULAR = (
    "ТИП ЗАДАЧИ: ОБЫЧНАЯ (regular).\n"
    "Как работать: участник читает входные данные из stdin (или входного файла) "
    "и печатает ответ в stdout (или выходной файл). Нужны: условие, валидатор, "
    "генератор, скрипт тестов, чекер (checker.cpp, обычно wcmp/основанный на "
    "testlib), основное правильное решение (тег MA) и набор неправильных решений "
    "(WA/TL/ML/RE) для проверки тестов. ИНТЕРАКТОР НЕ НУЖЕН. Раздела "
    "«Взаимодействие» в условии быть НЕ должно."
)

_INTERACTIVE = (
    "ТИП ЗАДАЧИ: ИНТЕРАКТИВНАЯ (interactive).\n"
    "Как работать: участник общается с программой-интерактором через stdin/stdout "
    "в реальном времени (запрос-ответ), а не читает фиксированный вход. "
    "ОБЯЗАТЕЛЬНО нужен интерактор (interactor.cpp на testlib: registerInteraction, "
    "общение с участником через cout+endl с flush, чтение ответов через ouf). "
    "Чекер работает в паре с интерактором. В условии ОБЯЗАТЕЛЕН раздел "
    "«Взаимодействие» (interaction) с описанием протокола: формат запросов, "
    "формат ответов, лимит на число запросов, требование flush после каждого "
    "вывода. Тесты задают сценарий/скрытые данные для интерактора."
)

_OUTPUT_ONLY = (
    "ТИП ЗАДАЧИ: OUTPUT-ONLY (вывод-только).\n"
    "Как работать: участник НЕ пишет программу — он сдаёт готовый файл с ответом "
    "на каждый тест. Оценивание частичное: scorer (ставится в Polygon как checker, "
    "на testlib с quitp(<баллы>, ...)) сравнивает вывод участника с эталоном и "
    "начисляет баллы пропорционально качеству. Эталонный ответ (*.a) производит "
    "решение-генератор ответа (jury_answer, тег MA), запускаемое при сборке. "
    "Баллы ВСЕГДА включены. Интерактор не нужен."
)

_GUIDES = {
    ProblemType.REGULAR: _REGULAR,
    ProblemType.INTERACTIVE: _INTERACTIVE,
    ProblemType.OUTPUT_ONLY: _OUTPUT_ONLY,
}


def guide(problem_type) -> str:
    """Return the guidance block for the given problem type (safe on bad input)."""
    try:
        pt = problem_type if isinstance(problem_type, ProblemType) else ProblemType(problem_type)
    except (ValueError, TypeError):
        pt = ProblemType.REGULAR
    return _GUIDES.get(pt, _REGULAR)
