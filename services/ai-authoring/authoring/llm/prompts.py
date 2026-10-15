"""Prompts of the authoring pipeline.

Every model call gets the problem materials (``sync.dossier``) as a separate,
cacheable message; the prompts below describe only the task and the output
format. Code must be ASCII: Polygon stores sources as cp1251, and Cyrillic
comments break the encoding.
"""
from __future__ import annotations

import json

from authoring.llm.client import Msg, Part

TESTLIB = (
    "Ты -- опытный автор задач по спортивному программированию и эксперт по testlib.h и Polygon. "
    "Ориентиры: https://codeforces.com/blog/entry/18291 (генераторы), "
    "https://codeforces.com/blog/entry/18426 (валидаторы), https://codeforces.com/blog/entry/18431 (чекеры), "
    "https://codeforces.com/blog/entry/18455 (интерактивные задачи). "
    'testlib подключается как #include "testlib.h". Код -- C++17/C++20 (g++), без нестандартных расширений.'
)

ASCII_RULE = (
    "Все комментарии и строковые литералы в коде -- только на английском (ASCII). "
    "Кириллица в исходниках ломает кодировку файлов в Polygon."
)

LATEX_RULES = (
    "Условие пишется в LaTeX-подмножестве Polygon, НЕ в Markdown: "
    "\\textbf{}, \\textit{}, \\texttt{}, $...$ и $$...$$ для формул, "
    "\\begin{itemize}\\item ...\\end{itemize}, \\begin{enumerate}, \\begin{tabular}{|c|c|}...\\end{tabular}, "
    "\\begin{center}, \\begin{lstlisting}...\\end{lstlisting} для кода, <<кавычки>>, --- для тире. "
    "Запрещены \\section, \\begin{verbatim}, markdown-разметка (`code`, **bold**, ```), \\\\ вне таблиц. "
    "Ограничения записывай точно: $1 \\le n \\le 2 \\cdot 10^5$."
)

FILES_PROTOCOL = (
    "ФОРМАТ ОТВЕТА -- теговые блоки, содержимое берётся дословно (без экранирования и без ```):\n"
    "<reply>Короткий ответ пользователю в Markdown: что сделано и почему.</reply>\n"
    '<file role="generator|validator|checker|interactor|solution|source" name="имя.cpp" tag="OK">'
    "ПОЛНЫЙ текст файла</file>   (tag -- только для решений: MA, OK, WA, TL, TO, ML, RE, PE, RJ)\n"
    '<statement lang="russian" field="legend|input|output|notes|scoring|interaction|tutorial|name">'
    "ПОЛНЫЙ новый текст раздела</statement>\n"
    "<script>ПОЛНЫЙ новый FreeMarker-скрипт генерации тестов</script>\n"
    '<limits time_limit="2000" memory_limit="256"/>\n'
    "<tags>тег1, тег2</tags>\n"
    '<checker standard="std::ncmp.cpp"/>   (стандартный чекер вместо своего)\n'
    "Выводи только изменённые файлы и разделы, каждый файл целиком (не diff). "
    "Имена существующих файлов не меняй, если об этом не просили."
)

SOLUTION_TAG_RULES = (
    "Теги решений = ожидаемый вердикт; Polygon при сборке проверяет, что решение его действительно получает. "
    "MA -- главное правильное решение (ровно одно), OK -- правильное, TO -- правильное или TL (безопасно для "
    "медленных переборов), WA/TL/ML/RE -- решение обязано получить этот вердикт хотя бы на одном тесте и не "
    "получать других ошибок. Вердикт должен возникать естественно из алгоритма: никаких while(true), sleep, "
    "assert(false), искусственных выделений памяти."
)

GENERATOR_RULES = (
    "Генератор: registerGen(argc, argv, 1); все параметры -- позиционные аргументы argv[1..]; ПОСЛЕДНИЙ аргумент -- "
    "уникальное число для различия тестов, его можно игнорировать (оно уже учтено в seed через registerGen). "
    "Используй rnd.next(...), rnd.shuffle(...), выводи тест в stdout через printf/cout, строго в формате ввода "
    "и строго в пределах ограничений (общих и своей группы). Никаких файлов и чтения stdin."
)

VALIDATOR_RULES = (
    "Валидатор: registerValidation(argc, argv); читай вход строго: inf.readInt(lo, hi, \"n\"), inf.readSpace(), "
    "inf.readEoln(), в конце inf.readEof(). Проверяй ВСЕ ограничения условия (включая суммарные и структурные: "
    "связность, различность и т.п.). Если в задаче есть группы, дополнительные ограничения группы проверяй через "
    "validator.group() (строка с именем группы, пустая для тестов без группы), например: "
    "if (validator.group() == \"1\") ensuref(n <= 10, \"group 1: n <= 10\");"
)

CHECKER_RULES = (
    "Чекер: если ответ однозначен и сравнивается напрямую, выбирай стандартный: std::ncmp.cpp (последовательность "
    "целых), std::wcmp.cpp (токены), std::lcmp.cpp (строки), std::rcmp6.cpp/rcmp9.cpp (вещественные), "
    "std::yesno.cpp / std::nyesno.cpp. Свой чекер (registerTestlibCmd) -- только когда ответов несколько: "
    "читай ответ жюри из ans и участника из ouf, проверяй корректность ответа участника, сравнивай оптимальность "
    "с ответом жюри (_fail, если участник нашёл лучше жюри), используй quitf(_ok/_wa/_pe, ...). "
    "Задача на оптимизацию с частичными баллами (в «Системе оценки» формула баллов от качества ответа): "
    "чекер-скорер -- проверь корректность вывода участника, посчитай целевую функцию и выставь баллы через "
    "quitp(score, ...); ответ жюри (ans) в таких задачах часто пустой -- опорное значение бери из входных данных."
)


def materials(dossier: str) -> Msg:
    """The problem materials, marked cacheable (stable prefix of every call)."""
    return Msg("user", [Part("Материалы задачи (актуальное состояние в Polygon):\n\n" + dossier, cache=True)])


def _history_text(history: list[dict]) -> str:
    rows = []
    for m in history:
        who = {"user": "Пользователь", "assistant": "Ассистент"}.get(m.get("role", ""), "Система")
        rows.append(f"{who}: {(m.get('content') or '').strip()[:3000]}")
    return "\n\n".join(rows)


# --------------------------------------------------------------------------- router
ROUTER_SYSTEM = (
    "Ты -- маршрутизатор запросов в чате автора задачи Polygon. По сообщению пользователя, контексту экрана и "
    "материалам задачи определи намерение и минимальный набор частей задачи, которые нужно трогать.\n"
    "Намерения:\n"
    "- question -- вопрос, объяснение, анализ, проверка, ревью БЕЗ просьбы что-то менять;\n"
    "- modify -- изменить конкретные части задачи (файлы, условие, лимиты, теги, скрипт);\n"
    "- generate -- создать задачу целиком с нуля по идее (условие, решение, валидатор, тесты); только если задача "
    "почти пустая или пользователь прямо просит сделать/пересоздать всё;\n"
    "- groups -- пользователь предлагает или просит подзадачи / группы тестов / разбалловку;\n"
    "- build -- собрать пакет, проверить, что задача собирается;\n"
    "- chat -- приветствие или разговор не о задаче.\n"
    "Цели (targets) выбирай из: statement, solution, validator, checker, interactor, generator, script, limits, "
    "tags, samples. Правило минимальности: если просят поменять генератор -- это generator (и script, только если "
    "меняется набор тестов), условие при этом НЕ трогается; если просят поправить условие -- только statement. "
    "Добавляй связанную цель лишь когда без неё изменение сломает задачу (например, новое ограничение в условии "
    "требует правки validator и generator).\n"
    'Ответь ТОЛЬКО JSON: {"intent": "...", "targets": ["..."], "summary": "задача одной фразой"}'
)


def router_messages(dossier: str, history: list[dict], text: str, context: dict | None) -> list[Msg]:
    ctx = ""
    if context:
        scope = context.get("scope")
        if scope == "file" and context.get("file"):
            ctx = f"Пользователь сейчас смотрит файл: {context['file']}."
        elif scope == "statement":
            ctx = "Пользователь сейчас смотрит условие."
    return [
        Msg.text("system", ROUTER_SYSTEM),
        materials(dossier),
        Msg.text(
            "user",
            (f"Предыдущие сообщения:\n{_history_text(history[-6:])}\n\n" if history else "")
            + (ctx + "\n" if ctx else "")
            + f"Новое сообщение пользователя:\n{text}",
        ),
    ]


# --------------------------------------------------------------------------- answer
ANSWER_SYSTEM = (
    f"{TESTLIB}\nОтвечай на вопрос пользователя о его задаче по-русски, в Markdown, опираясь на материалы задачи. "
    "Цитируй конкретные места файлов, если это помогает. Если видишь ошибку -- скажи, где она и как её исправить, "
    "но сами файлы не переписывай: пользователь попросит отдельно. Будь конкретен и краток."
)


def answer_messages(dossier: str, history: list[dict], text: str) -> list[Msg]:
    return [
        Msg.text("system", ANSWER_SYSTEM),
        materials(dossier),
        Msg.text(
            "user",
            (f"История чата:\n{_history_text(history[-10:])}\n\n" if history else "") + f"Вопрос:\n{text}",
        ),
    ]


# --------------------------------------------------------------------------- modify
def modify_system(targets: list[str], problem_type: str) -> str:
    return (
        f"{TESTLIB}\nТы вносишь изменения в задачу по просьбе пользователя. Тип задачи: {problem_type}.\n"
        f"РАЗРЕШЕНО менять ТОЛЬКО: {', '.join(targets)}. Всё остальное оставь как есть, даже если хочется "
        "улучшить -- можно упомянуть это в <reply>.\n"
        f"{ASCII_RULE}\n{LATEX_RULES}\n{SOLUTION_TAG_RULES}\n{GENERATOR_RULES}\n{VALIDATOR_RULES}\n"
        "Скрипт генерации: FreeMarker, каждая строка вида `gen arg1 arg2 > $` -- генератор вызывается по имени "
        "файла без расширения; все строки должны различаться (используй ${i} в <#list 1..k as i>).\n"
        f"{FILES_PROTOCOL}"
    )


def modify_messages(
    dossier: str, history: list[dict], text: str, targets: list[str], problem_type: str
) -> list[Msg]:
    return [
        Msg.text("system", modify_system(targets, problem_type)),
        materials(dossier),
        Msg.text(
            "user",
            (f"История чата:\n{_history_text(history[-10:])}\n\n" if history else "")
            + f"Запрос пользователя:\n{text}",
        ),
    ]


# --------------------------------------------------------------------------- repair
REPAIR_SYSTEM = (
    f"{TESTLIB}\nСборка пакета задачи в Polygon упала. По логу ошибки найди причину и исправь МИНИМАЛЬНЫМ изменением "
    "соответствующих файлов (генератор, скрипт, валидатор, чекер, решения, примеры). Типичные причины: ошибка "
    "компиляции; валидатор отвергает тест (виноват генератор/скрипт или сам валидатор слишком строгий -- сверься с "
    "условием); одинаковые тесты в скрипте; решение с тегом получает не тот вердикт; чекер падает; превышение "
    "ограничений генератором. Условие меняй только если ошибка именно в нём (например, неверный пример). "
    "Не скрывай ошибку ослаблением проверок: валидатор должен соответствовать условию.\n"
    f"{ASCII_RULE}\n{SOLUTION_TAG_RULES}\n{GENERATOR_RULES}\n{VALIDATOR_RULES}\n{FILES_PROTOCOL}"
)


def repair_messages(dossier: str, error: str, attempt: int, previous_fixes: list[str]) -> list[Msg]:
    tail = ""
    if previous_fixes:
        tail = "\n\nПредыдущие попытки починки (не повторяй их, если они не помогли):\n" + "\n".join(
            f"- {f}" for f in previous_fixes
        )
    return [
        Msg.text("system", REPAIR_SYSTEM),
        materials(dossier),
        Msg.text("user", f"Попытка починки №{attempt}. Лог ошибки сборки:\n```\n{error[:12000]}\n```{tail}"),
    ]


# --------------------------------------------------------------------------- generation
STATEMENT_SYSTEM = (
    f"{TESTLIB}\nПо идее пользователя составь полное условие задачи на русском.\n{LATEX_RULES}\n"
    "Ответ -- теговые блоки:\n"
    '<statement lang="russian" field="name">Название</statement>\n'
    '<statement lang="russian" field="legend">Легенда с формальной постановкой</statement>\n'
    '<statement lang="russian" field="input">Формат ввода с точными ограничениями</statement>\n'
    '<statement lang="russian" field="output">Формат вывода</statement>\n'
    '<statement lang="russian" field="notes">Пояснение к примерам (можно пустым не выводить)</statement>\n'
    '<limits time_limit="1000" memory_limit="256"/>\n'
    "<sample>вход первого примера</sample> (1-3 примера, маленьких и показательных; ответы посчитает решение)\n"
    "<tags>теги по алгоритмам, через запятую</tags>\n"
    "<reply>1-2 фразы: что за задача и какая идея решения</reply>\n"
    "Лимиты подбирай так, чтобы авторское решение проходило с запасом в 2-3 раза, а неоптимальные -- нет."
)


def statement_messages(idea: str, problem_type: str, extra: str = "") -> list[Msg]:
    return [
        Msg.text("system", STATEMENT_SYSTEM),
        Msg.text(
            "user",
            f"Тип задачи: {problem_type}.\nИдея:\n{idea}" + (f"\n\nДополнительно:\n{extra}" if extra else ""),
        ),
    ]


def single_file_system(what: str, rules: str) -> str:
    return (
        f"{TESTLIB}\n{what}\n{rules}\n{ASCII_RULE}\n"
        'Ответ -- один блок <file role="..." name="..." tag="...">полный код</file> и при желании <reply>.'
    )


MAIN_SOLUTION_SYSTEM = single_file_system(
    "Напиши авторское (главное) решение задачи: асимптотически оптимальное, аккуратное, без UB, с быстрым вводом.",
    'Блок: <file role="solution" name="main.cpp" tag="MA">. Решение читает stdin и пишет stdout (или файлы, если '
    "так в параметрах задачи).",
)

BRUTE_SYSTEM = single_file_system(
    "Напиши простое заведомо правильное переборное решение (для проверки авторского): максимально простое, "
    "пусть медленное.",
    'Блок: <file role="solution" name="brute.cpp" tag="TO"> -- тег TO означает «правильно или TL», так что на '
    "больших тестах оно может не успевать.",
)

VALIDATOR_SYSTEM = single_file_system(
    "Напиши валидатор входных данных строго по условию.",
    VALIDATOR_RULES + ' Блок: <file role="validator" name="validator.cpp">.',
)

CHECKER_SYSTEM = (
    f"{TESTLIB}\nВыбери чекер для задачи.\n{CHECKER_RULES}\n{ASCII_RULE}\n"
    'Ответ: либо <checker standard="std::ncmp.cpp"/>, либо <file role="checker" name="checker.cpp">код</file>; '
    "плюс <reply> с одной фразой обоснования."
)


def file_messages(system: str, dossier: str, task: str = "") -> list[Msg]:
    msgs = [Msg.text("system", system), materials(dossier)]
    msgs.append(Msg.text("user", task or "Выполни задачу по материалам."))
    return msgs


PLAN_SYSTEM = (
    f"{TESTLIB}\nСоставь план тестов задачи в JSON.\n"
    "Если пользователь задал группы/баллы -- следуй им точно. Если групп нет и их не просили -- одна неявная группа.\n"
    "Схема ответа (ТОЛЬКО JSON):\n"
    '{"use_groups": true|false,\n'
    ' "groups": [\n'
    '   {"name": "0", "samples": true, "points": 0, "description": "тесты из условия"},\n'
    '   {"name": "1", "points": 30, "description": "$n \\\\le 10$", "dependencies": ["0"],\n'
    '    "generator": "gen_small", "cases": [{"args": "10 random", "count": 4}, {"args": "10 max", "count": 1}]},\n'
    "   ...\n"
    " ],\n"
    ' "note": "кратко о покрытии"}\n'
    "Правила: имена групп -- короткие (0, 1, 2, ...); сумма баллов обычно 100; группа примеров (samples=true) "
    "имеет 0 баллов и не имеет cases; dependencies ссылаются только на группы выше по списку (обычно группа "
    "зависит от групп с более слабыми ограничениями и от группы примеров); generator -- имя генератора "
    "(латиница, цифры, _), можно переиспользовать один генератор в нескольких группах; args -- позиционные "
    "аргументы генератора через пробел (без уникализирующего номера, его добавим сами); count -- число тестов. "
    "Покрой минимальные, максимальные, крайние, специальные и случайные случаи; 5-25 тестов на группу. "
    "Без групп (use_groups=false): одна группа с name \"main\", points 0."
)


def plan_messages(dossier: str, request: str) -> list[Msg]:
    return [
        Msg.text("system", PLAN_SYSTEM),
        materials(dossier),
        Msg.text("user", request or "Составь план тестов по условию."),
    ]


def generator_system() -> str:
    return single_file_system(
        "Напиши генератор тестов на testlib.",
        GENERATOR_RULES,
    )


def generator_task(name: str, groups: list[dict]) -> str:
    lines = [f"Генератор: {name}.cpp (вызывается в скрипте как `{name} <args> <уникальный номер>`)."]
    for g in groups:
        lines.append(
            f"Группа {g['name']}: {g.get('description') or 'без доп. ограничений'}. Вызовы (args):"
        )
        for case in g.get("cases") or []:
            lines.append(f"  - `{name} {case['args']} N` x{case['count']}")
    lines.append(
        "Сделай так, чтобы каждый вызов давал корректный тест своей группы. "
        f'Блок: <file role="generator" name="{name}.cpp">.'
    )
    return "\n".join(lines)


VALIDATOR_GROUPS_TASK = (
    "В задаче появились группы тестов (см. план ниже). Обнови валидатор: оставь все общие проверки и добавь "
    "проверку дополнительных ограничений каждой группы через validator.group(). Тесты группы примеров "
    "проверяются только общими ограничениями."
)


def plan_text(plan: dict) -> str:
    return json.dumps(plan, ensure_ascii=False, indent=1)
