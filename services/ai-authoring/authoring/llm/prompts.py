"""Prompts of the authoring pipeline.

Every model call gets the problem materials (``sync.dossier``) as a separate,
cacheable message; the prompts below describe only the task and the output
format. Code must be ASCII: Polygon stores sources as cp1251, and Cyrillic
comments break the encoding.
"""
from __future__ import annotations

import json

from authoring.llm.client import Msg, Part
from authoring.llm.problem_types import INTERACTIVE, OUTPUT_ONLY, OUTPUT_ONLY_TEST_POINTS, normalize_type

TESTLIB = (
    "Ты -- опытный автор задач по спортивному программированию и эксперт по testlib.h и Polygon. "
    "Ориентиры: https://codeforces.com/blog/entry/18291 (генераторы), "
    "https://codeforces.com/blog/entry/18426 (валидаторы), https://codeforces.com/blog/entry/18431 (чекеры), "
    "https://codeforces.com/blog/entry/18455 (интерактивные задачи). "
    'testlib подключается как #include "testlib.h". Код -- C++17/C++20 (g++), без нестандартных расширений. '
    "Подключай явно все используемые стандартные заголовки (<string>, <vector>, <algorithm>, ...) или "
    "<bits/stdc++.h>: Polygon компилирует строго, неявные include'ы не срабатывают."
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
    "ПОЛНЫЙ текст файла</file>   (tag -- только для решений: MA, OK, WA, TL, TO, ML, TM, RE, PE, RJ, NR)\n"
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
    "Теги решений = ожидаемый вердикт; Polygon при сборке пакета прогоняет каждое решение на всех тестах и "
    "проверяет, что вердикт совпадает с тегом, иначе сборка падает. Значения тегов:\n"
    "- MA -- главное правильное решение (ровно одно на задачу), OK -- правильное, проходит всё;\n"
    "- TO -- правильное ИЛИ превышает время (OK либо TL): тег для медленного, но верного перебора, который на "
    "больших тестах может не успеть; это НЕ TL;\n"
    "- TL -- ОБЯЗАНО превысить ограничение времени хотя бы на одном тесте (и не получить WA/RE/ML ни на одном): "
    "например, O(n^2) при n = 10^5 и TL 1-2 с; если на всех тестах успевает -- сборка падает;\n"
    "- ML -- обязано превысить память хотя бы на одном тесте (например, таблица O(n^2) или O(n*W) при больших "
    "n), TM -- превышает время или память;\n"
    "- WA -- обязано дать неверный ответ хотя бы на одном тесте (типичная ошибка: не тот крайний случай, "
    "переполнение int, жадность вместо ДП), PE -- ошибка формата вывода, RE -- ошибка исполнения "
    "(выход за массив при максимальном n, переполнение стека глубокой рекурсией), RJ -- любой неверный вердикт;\n"
    "- NR -- решение не запускается при сборке (черновик).\n"
    "Вердикт должен возникать естественно из алгоритма и ДЕТЕРМИНИРОВАННО на имеющихся тестах (сверься с "
    "ограничениями, лимитами и тестами из материалов): никаких while(true), sleep, assert(false), выделения "
    "памяти «просто так»."
)

NEW_SOLUTION_RULES = (
    "Если просят написать/добавить решение (в том числе неверное, медленное, жрущее память, с ошибкой), "
    "создай НОВЫЙ файл решения с подходящим тегом и говорящим именем (например tl_n2.cpp, wa_overflow.cpp, "
    "ml_table.cpp, ok_slow.cpp), а существующие решения (особенно главное MA) не переписывай, если об этом "
    "прямо не просили. Тег выбирай строго по смыслу (см. значения тегов) и проверь по ограничениям и тестам, "
    "что вердикт гарантирован; в <reply> одной фразой объясни, почему решение получит этот вердикт."
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
    "Просьба написать/добавить/сгенерировать решение (правильное, медленное, неверное, «не должно проходить по "
    "времени/памяти», с тегом TL/WA/ML/RE/TO и т.п.) -- это modify с целью solution.\n"
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


def type_rules(problem_type: str) -> str:
    """Short type-specific rules for edits and repairs (the full guide is in the materials)."""
    kind = normalize_type(problem_type)
    if kind == INTERACTIVE:
        return (
            "Задача интерактивная: интерактор -- <file role=\"interactor\" ...>, решения обязаны делать flush после "
            "каждого вывода, генератор и валидатор работают со скрытыми данными интерактора, протокол -- в разделе "
            "условия interaction."
        )
    if kind == OUTPUT_ONLY:
        return (
            "Задача output-only: чекер -- это скорер (quitp с баллами 0.."
            f"{OUTPUT_ONLY_TEST_POINTS} за тест), MA -- эталонный решатель жюри, формула баллов в разделе scoring "
            "должна совпадать со скорером."
        )
    return ""


# --------------------------------------------------------------------------- modify
def modify_system(targets: list[str], problem_type: str) -> str:
    return (
        f"{TESTLIB}\nТы вносишь изменения в задачу по просьбе пользователя. Тип задачи: {problem_type}.\n"
        f"РАЗРЕШЕНО менять ТОЛЬКО: {', '.join(targets)}. Всё остальное оставь как есть, даже если хочется "
        "улучшить -- можно упомянуть это в <reply>.\n"
        f"{ASCII_RULE}\n{LATEX_RULES}\n{SOLUTION_TAG_RULES}\n{NEW_SOLUTION_RULES}\n{GENERATOR_RULES}\n"
        f"{VALIDATOR_RULES}\n{type_rules(problem_type)}\n"
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
    "ограничений генератором; в интерактивной задаче -- интерактор (протокол, flush, лимит запросов) или "
    "решение без flush; в output-only -- скорер (чекер с quitp) или эталонное решение MA. "
    "Условие меняй только если ошибка именно в нём (например, неверный пример). "
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
    "Лимиты подбирай так, чтобы авторское решение проходило с запасом в 2-3 раза, а неоптимальные -- нет.\n"
    "Уточняющих вопросов не задавай: если в идее чего-то не хватает (точная версия алгоритма, формат, "
    "ограничения), сам выбери разумный вариант, зафиксируй его в условии и перечисли допущения в <reply>. "
    "Блоки name, legend, input и output обязательны в любом случае."
)

STATEMENT_RETRY = (
    'В ответе нет блока <statement lang="russian" field="legend"> (или ответ оборвался). Не задавай вопросов: '
    "прими разумные допущения сами и верни ПОЛНЫЙ ответ заново в теговых блоках -- name, legend, input, output, "
    "notes, limits, sample, tags, reply. Пиши компактно."
)


STATEMENT_TYPE_RULES = {
    INTERACTIVE: (
        "Задача ИНТЕРАКТИВНАЯ. Дополнительно обязателен блок "
        '<statement lang="russian" field="interaction">протокол взаимодействия</statement>: формат запросов '
        "участника и ответов жюри, лимит числа запросов, как сообщить итоговый ответ, требование flush после "
        "каждого вывода (cout << endl или fflush(stdout)), адаптивный ли интерактор. В input -- что программа "
        "получает в начале (или что ничего не получает), в output -- формат итогового ответа; пример диалога -- в "
        "notes. Блоки <sample> -- это СКРЫТЫЕ данные для интерактора (формат входного файла теста, который "
        "ты опишешь в <reply>), а не то, что видит участник."
    ),
    OUTPUT_ONLY: (
        "Задача OUTPUT-ONLY: участник получает все входные файлы и сдаёт ответ на каждый. Обычно это задача на "
        "оптимизацию с частичными баллами или NP-трудная задача без требования оптимума. В input -- формат "
        "входного файла, в output -- формат ответа, который сдаёт участник. Дополнительно обязателен блок "
        '<statement lang="russian" field="scoring">: что сдаётся, целевая функция, формула баллов за тест '
        f"(максимум {OUTPUT_ONLY_TEST_POINTS} баллов за тест: полный балл за ответ не хуже ответа жюри, иначе "
        "пропорциональная доля; некорректный ответ -- 0), итог -- сумма по тестам. Лимиты времени/памяти "
        "указывай обычные (они относятся к эталонному решателю жюри)."
    ),
}


def statement_messages(idea: str, problem_type: str, extra: str = "") -> list[Msg]:
    kind = normalize_type(problem_type)
    system = STATEMENT_SYSTEM + ("\n" + STATEMENT_TYPE_RULES[kind] if kind in STATEMENT_TYPE_RULES else "")
    return [
        Msg.text("system", system),
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

# interactive problems: the main solution talks to the interactor
INTERACTIVE_MAIN_SOLUTION_SYSTEM = single_file_system(
    "Напиши авторское (главное) решение ИНТЕРАКТИВНОЙ задачи строго по протоколу из раздела «Взаимодействие»: "
    "оптимальное по числу запросов и времени, без UB.",
    'Блок: <file role="solution" name="main.cpp" tag="MA">. Читай ответы жюри из stdin, запросы печатай в stdout '
    "и делай flush после КАЖДОГО вывода (cout << ... << endl или fflush(stdout)); не превышай лимит запросов.",
)

INTERACTOR_SYSTEM = single_file_system(
    "Напиши интерактор для ИНТЕРАКТИВНОЙ задачи Polygon на testlib.",
    "Требования: registerInteraction(argc, argv); прочитай скрытые данные теста из inf (ровно в том формате, "
    "который генерирует генератор и проверяет валидатор); общайся с участником: его запросы читай из ouf "
    "(ouf.readInt(lo, hi, \"name\") и т.п. с границами из условия), ответы печатай в cout с endl (flush); "
    "проверяй корректность запросов и лимит их числа -- при нарушении quitf(_wa, ...) или quitf(_pe, ...); "
    "адаптивность -- как в условии. В конце запиши в tout итог (например, итоговый ответ участника) -- его "
    "сравнит чекер с таким же итогом главного решения, -- и заверши quitf(_ok, ...). "
    'Блок: <file role="interactor" name="interactor.cpp">.',
)

INTERACTIVE_CHECKER_SYSTEM = (
    f"{TESTLIB}\nВыбери чекер для ИНТЕРАКТИВНОЙ задачи. В Polygon чекер получает вывод интерактора в tout как ouf "
    "(для решения участника) и как ans (для главного решения), вход -- inf. Если интерактор сам проверяет всё и "
    "пишет в tout однозначный итог, достаточно стандартного <checker standard=\"std::wcmp.cpp\"/>; иначе напиши "
    "свой чекер (registerTestlibCmd), который сверяет итог из ouf с ans/inf.\n"
    f"{ASCII_RULE}\n"
    'Ответ: либо <checker standard="std::wcmp.cpp"/>, либо <file role="checker" name="checker.cpp">код</file>; '
    "плюс <reply> с одной фразой обоснования."
)

# output-only problems: the MA solution produces the jury answers (*.a)
JURY_SOLUTION_SYSTEM = single_file_system(
    "Напиши эталонный решатель жюри для OUTPUT-ONLY задачи: его вывод по входному файлу станет ответом жюри "
    "(*.a), с которым скорер сравнивает ответы участников. Ответ должен быть корректным и как можно лучше по "
    "целевой функции (оптимальным, если это реально за лимит времени).",
    'Блок: <file role="solution" name="main.cpp" tag="MA">. Читает stdin, пишет stdout.',
)

SCORER_EXAMPLE = r'''#include "testlib.h"
#include <bits/stdc++.h>
using namespace std;

const double MAX_POINTS = 10.0;  // max points of one test

int n;
vector<long long> a;

// reads and checks an answer, returns its objective; quits with _wa on any violation
long long readAnswer(InStream& stream) {
    int k = stream.readInt(1, n, "k");
    set<int> used;
    long long value = 0;
    for (int i = 0; i < k; i++) {
        int v = stream.readInt(1, n, "v[" + to_string(i) + "]");
        stream.quitif(used.count(v), _wa, "vertex %d is repeated", v);
        used.insert(v);
        value += a[v - 1];
    }
    return value;
}

int main(int argc, char* argv[]) {
    registerTestlibCmd(argc, argv);
    n = inf.readInt();
    a.resize(n);
    for (auto& x : a) x = inf.readLong();
    long long jury = readAnswer(ans);
    long long participant = readAnswer(ouf);
    if (participant >= jury) quitp(MAX_POINTS, "optimal: %lld", participant);
    double points = floor(MAX_POINTS * double(participant) / double(jury) * 100.0) / 100.0;
    quitp(points, "participant %lld, jury %lld", participant, jury);
}'''

SCORER_SYSTEM = single_file_system(
    "Напиши чекер-скорер для OUTPUT-ONLY задачи на testlib: он начисляет частичные баллы за ответ участника.",
    "Требования: registerTestlibCmd(argc, argv); тест читай из inf, ответ жюри (вывод эталонного решателя) -- из "
    "ans, ответ участника -- из ouf; ответ участника структурно проверяй (ouf.readInt/readLong с границами, "
    "ouf.quitif(cond, _wa, ...)); ответ жюри читай той же функцией (если он некорректен, testlib сам выдаст "
    "_fail); посчитай целевую функцию и выстави баллы через quitp(<double>, ...) -- АБСОЛЮТНЫЕ баллы теста от 0 "
    f"до {OUTPUT_ONLY_TEST_POINTS}: полный балл, если ответ не хуже жюри, иначе пропорциональная доля по формуле "
    "из раздела «Система оценки» (никогда не больше, чем заслуживает ответ). Используй именно quitp, а не "
    "quitf(_ok). Пример стиля (задача другая!):\n"
    f"```\n{SCORER_EXAMPLE}\n```\n"
    'Блок: <file role="checker" name="scorer.cpp">.',
)


def main_solution_system(problem_type: str) -> str:
    kind = normalize_type(problem_type)
    if kind == INTERACTIVE:
        return INTERACTIVE_MAIN_SOLUTION_SYSTEM
    if kind == OUTPUT_ONLY:
        return JURY_SOLUTION_SYSTEM
    return MAIN_SOLUTION_SYSTEM


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


PLAN_TYPE_RULES = {
    INTERACTIVE: (
        "Задача интерактивная: каждый тест -- СКРЫТЫЕ данные для интерактора (формат -- как у примеров и "
        "валидатора), генераторы выдают именно их. Покрой случаи, на которых неоптимальная стратегия запросов "
        "превышает лимит."
    ),
    OUTPUT_ONLY: (
        "Задача output-only: группы НЕ нужны (use_groups=false, одна группа \"main\"), баллы за тесты расставит "
        "система; обычно 5-20 тестов разного размера и структуры, от маленьких до максимальных."
    ),
}


def plan_messages(dossier: str, request: str, problem_type: str = "regular") -> list[Msg]:
    kind = normalize_type(problem_type)
    system = PLAN_SYSTEM + ("\n" + PLAN_TYPE_RULES[kind] if kind in PLAN_TYPE_RULES else "")
    return [
        Msg.text("system", system),
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
