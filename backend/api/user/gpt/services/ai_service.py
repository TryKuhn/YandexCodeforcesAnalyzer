import json
import logging
import re
from typing import Any, Dict, List

import httpx
from fastapi import HTTPException

from settings import settings

logger = logging.getLogger(__name__)

MAX_IDEA_CHARS = 50_000

_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\r?\n?|```\s*$", re.MULTILINE)


def _strip_code_fences(code: str) -> str:
    return _CODE_FENCE_RE.sub("", code).strip()


class TaskAIService:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        base_url = settings.OPENAI_HOST.rstrip("/")
        self.url = (
            f"{base_url}/chat/completions"
            if not base_url.endswith("/chat/completions")
            else base_url
        )

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://judge-system.com",
            "X-Title": "Judge System AI",
        }

    async def _base_ask(
        self, model: str, messages: List[Dict], json_mode: bool = True
    ) -> Dict:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    self.url, headers=self.headers, json=payload
                )
                if response.status_code != 200:
                    logger.error(
                        f"AI API Error: {response.status_code} - {response.text}"
                    )
                    raise HTTPException(
                        status_code=500, detail=f"AI Service error: {response.text}"
                    )

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                if json_mode:
                    content = content.strip()
                    content = re.sub(
                        r"^```(?:json)?\n?|```$", "", content, flags=re.MULTILINE
                    ).strip()
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        match = re.search(r"\{.*\}", content, re.DOTALL)
                        if match:
                            return json.loads(match.group())
                        raise
                else:
                    return {"text": content}
            except HTTPException:
                raise
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.error(f"AI Service network error: {e}")
                raise HTTPException(status_code=503, detail="AI service unavailable: network error")
            except Exception as e:
                logger.error(f"AI Service Exception: {e}")
                raise HTTPException(status_code=500, detail=f"AI service error: {e}")

    async def generate_statement(
        self, user_idea: str, model: str, user_prompt: str, history: List[Dict]
    ) -> Dict:
        if len(user_idea) > MAX_IDEA_CHARS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Текст слишком длинный ({len(user_idea)} символов). "
                    f"Максимум — {MAX_IDEA_CHARS} символов."
                ),
            )

        system_prompt = (
            "Вы — автор задач по спортивному программированию. "
            "ПРАВИЛО: Пишите условия максимально простым и понятным языком, доступным школьнику. "
            "Избегайте излишней математической терминологии, если это возможно. "
            "ФОРМАТИРОВАНИЕ — ТОЛЬКО LaTeX, никакого Markdown:\n"
            "- жирный текст: \\textbf{текст}, НЕ **текст**\n"
            "- курсив: \\textit{текст}, НЕ *текст*\n"
            "- моноширинный/код: \\texttt{текст}, НЕ `текст`\n"
            "- математика: $формула$, как обычно\n"
            "- списки: не используй Markdown-списки (- item), пиши связным текстом или через enumerate/itemize LaTeX\n"
            "Выводите ТОЛЬКО JSON: {name, legend, input, output, notes, tutorial}."
        )

        final_prompt = user_prompt or system_prompt

        messages = [{"role": "system", "content": final_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_idea})

        return await self._base_ask(model, messages)

    async def generate_technical_stuff(
        self, approved_statement: Dict, model: str
    ) -> Dict:
        system_prompt = (
            "Ты — эксперт по testlib.h и разработке задач для спортивного программирования. "
            "Можешь использовать следующие ресурсы для генерации технических файлов: "
            "https://codeforces.com/blog/entry/18289 (статья о testlib), "
            "https://codeforces.com/blog/entry/18291 (статья о генерации тестов), "
            "https://codeforces.com/blog/entry/18426 (статья о валидаторах), "
            "https://codeforces.com/blog/entry/18431 (статья о чекерах). "
            "На основе условия задачи создай технические файлы для Polygon. "
            "Нужно сгенерировать: validator.cpp, generator.cpp, checker.cpp, "
            "solution.cpp (Main, C++), solution.py (Python-решение, тег OK), а также решения с тегами: "
            "WA, TL, RE, ML. "
            "\n\nПРАВИЛА ДЛЯ НЕКОРРЕКТНЫХ РЕШЕНИЙ (ОБЯЗАТЕЛЬНО СОБЛЮДАТЬ):"
            "\n- tl_sol (TL): Напиши ПРАВИЛЬНОЕ решение задачи, но используй заведомо медленный алгоритм — "
            "вложенные циклы O(n²) или O(n³) там, где возможен O(n log n) или O(n). "
            "Например: сортировка пузырьком, перебор всех пар, полный перебор подмножеств. "
            "ЗАПРЕЩЕНО: sleep(), busy-loop, искусственные задержки. "
            "Результат должен быть ВЕРНЫМ на малых тестах, но превышать TL на больших."
            "\n- ml_sol (ML): Напиши ПРАВИЛЬНОЕ решение задачи, но с избыточным расходом памяти — "
            "используй O(n²) памяти там, где достаточно O(n). "
            "Например: храни всю матрицу пар вместо одномерного массива, "
            "или создавай n копий входного массива, или используй map/set с парами. "
            "ЗАПРЕЩЕНО: new int[1000000000], искусственное выделение памяти не по алгоритму. "
            "Результат должен быть ВЕРНЫМ на малых тестах, но превышать ML на больших."
            "\n- wa_sol (WA): Напиши НЕВЕРНОЕ решение — алгоритм с правдоподобной, но ошибочной логикой. "
            "Например: жадный алгоритм там, где нужна DP; игнорирование граничных случаев; "
            "неверная формула для подсчёта. Решение должно давать WA хотя бы на части тестов."
            "\n- re_sol (RE): Напиши решение, которое вызовет Runtime Error на некоторых тестах — "
            "например, обращение к вектору по индексу без проверки границ, деление на ноль при определённых входных данных, "
            "stack overflow от рекурсии без базового случая. "
            "Выведи JSON: {validator, generator, checker, solution_py, solution_cpp,"
            "wa_sol, tl_sol, re_sol, ml_sol, script}. "
            "КРИТИЧЕСКИ ВАЖНО: все строковые значения в JSON — это чистый исходный код. "
            "НЕ оборачивай код в markdown (никаких ```cpp, ```, ~~~ и т.п.). "
            "Только сырой текст файла, без какого-либо форматирования."
            "Обрати внимание на правила использования script для генерации тестов в Polygon: "
            "Freemarker Template Engine is an engine, created to process text files. "
            "It process only parts of text files, that are surrounded with special Freemarker directives. "
            "Everything else is copied directly to the output. "
            "So if the file does not contain Freemarker at all, "
            "that the result of the processing such file is an exact copy of this file."
            "Input:"
            "gen 100 100 1 > 1"
            "gen 100 100 2 > 2"
            "gen 100 100 3 > 3"
            "gen 100 100 4 > 4"
            "Output:"
            "gen 100 100 1 > 1"
            "gen 100 100 2 > 2"
            "gen 100 100 3 > 3"
            "gen 100 100 4 > 4"
            "Variables are created automatically during their first assignment. To assign a value to the variable #assign directive is used."
            "<#assign i = 10/>"
            "To evaluate some expression with variables you should enclose it in ${} symbols."
            "<#assign i = 10/>"
            "gen ${i} ${i*2 + 1} ${i*i + 10} > $"
            "Input:"
            "<#assign i = 2/>"
            "<#assign j = 3/>"
            "gen ${i} ${j} ${i + j} ${i*j + i + j + 2} > $"
            "<#assign i2 = i*i/>"
            "<#assign j2 = j*j/>"
            "gen ${i2} ${j2} > $"
            "Output:"
            "gen 2 3 5 13 > $"
            "gen 4 9 > $"
            "To iterate through the range of integers, #list directive is used."
            "<#list 10..20 as iter></#list>"
            "For example:"
            "<#list 10..20 as iter>"
            "gen 100 200 ${iter*iter + 10} > $"
            "</#list>"
            "Of course, loops can be nested. And all variables, that were declared previously, can be used inside."
            "Input:"
            "<#assign maxN = 1/>"
            "<#list 1..5 as power>"
            "<#assign maxN = maxN * 10>"
            "<#list 1..5 as testNumber>"
            "generatorFile ${maxN} abacaba ${testNumber} > $"
            "</#list>"
            "</#list>"
            "Output:"
            "generatorFile 10 abacaba 1 > $"
            "generatorFile 10 abacaba 2 > $"
            "generatorFile 10 abacaba 3 > $"
            "generatorFile 10 abacaba 4 > $"
            "generatorFile 10 abacaba 5 > $"
            "generatorFile 100 abacaba 1 > $"
            "generatorFile 100 abacaba 2 > $"
            "generatorFile 100 abacaba 3 > $"
            "generatorFile 100 abacaba 4 > $"
            "generatorFile 100 abacaba 5 > $"
            "generatorFile 1000 abacaba 1 > $"
            "generatorFile 1000 abacaba 2 > $"
            "generatorFile 1000 abacaba 3 > $"
            "generatorFile 1000 abacaba 4 > $"
            "generatorFile 1000 abacaba 5 > $"
            "generatorFile 10000 abacaba 1 > $"
            "generatorFile 10000 abacaba 2 > $"
            "generatorFile 10000 abacaba 3 > $"
            "generatorFile 10000 abacaba 4 > $"
            "generatorFile 10000 abacaba 5 > $"
            "generatorFile 100000 abacaba 1 > $"
            "generatorFile 100000 abacaba 2 > $"
            "generatorFile 100000 abacaba 3 > $"
            "generatorFile 100000 abacaba 4 > $"
            "generatorFile 100000 abacaba 5 > $"
            "For more detailed tutorial please see Freemarker Documentation"
            "Мы пишем файл generator.cpp, поэтому и вызывать должны генерацию тестов через generator. "
            "Учитывай, что нельзя использовать одинаковые скрипты для генерации разных тестов, "
            "необходимо хотя бы создать фиктивную переменную, которая будет отличать эти тесты. "
            "Внимательно проверяй, чтобы в скрипте любая пара тестов отличалась хотя бы фиктивной переменной. "
            "Учти, что если ты создаёшь фиктивную переменную, которая не влияет на генерацию тестов, то её всё равно "
            "по правилам полигона нужно использовать в генераторе тестов (можно просто объявить её в коде). "
            "Также учитывай, что параметры скрипта ты можешь использовать для генерации тестов."
            "Например, если в условии задачи есть ограничения на n, "
            "то ты можешь использовать эти ограничения в скрипте для генерации тестов. "
            "Также по возможности требуется сделать тесты максимально разнообразными, чтобы покрыть все возможные случаи. "
            "И помни, что скрипт должен генерировать тесты,"
            "которые соответствуют условию задачи и не выходят за рамки ограничений. "
        )

        user_prompt = (
            f"Problem Statement:\n{json.dumps(approved_statement, ensure_ascii=False)}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await self._base_ask(model, messages)
        return {
            k: _strip_code_fences(v) if isinstance(v, str) else v
            for k, v in result.items()
        }

    async def fix_code(
        self,
        error: str,
        component: str,
        code: str,
        statement: Dict,
        model: str,
        previous_errors: List[str] | None = None,
    ) -> str:
        history_note = ""
        if previous_errors:
            history_note = (
                "\n\nПРЕДЫДУЩИЕ ПОПЫТКИ ИСПРАВЛЕНИЯ ТОЖЕ НЕ ПОМОГЛИ:\n"
                + "\n".join(f"- {e}" for e in previous_errors)
                + "\nПопробуй принципиально другой подход."
            )
        system_prompt = (
            f"Fix the {component} code for the Polygon judge system. "
            f"Current error: {error}{history_note} "
            "Return ONLY the corrected code without any explanation or markdown."
        )
        user_prompt = (
            f"Statement:\n{json.dumps(statement, ensure_ascii=False)}\n\nBroken code:\n{code}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await self._base_ask(model, messages, json_mode=False)
        return result["text"].strip()

    async def post_build_refine(
        self,
        message: str,
        statement: Dict,
        current_files: Dict[str, str],
        model: str,
    ) -> Dict[str, str]:
        files_text = "\n\n".join(
            f"=== {key} ===\n{content}"
            for key, content in current_files.items()
        )
        system_prompt = (
            "Ты — эксперт по задачам Polygon. Пользователь хочет доработать уже созданную задачу. "
            "Проанализируй его запрос и обнови только те файлы, которых касаются изменения. "
            "Верни JSON, где ключи — имена изменённых файлов (из набора: "
            "validator, generator, checker, solution_cpp, solution_py, wa_sol, tl_sol, re_sol, ml_sol, script), "
            "а значения — полные обновлённые версии этих файлов. "
            "Не включай в ответ файлы, которые не нужно менять."
        )
        user_prompt = (
            f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}\n\n"
            f"Текущие файлы:\n{files_text}\n\n"
            f"Запрос пользователя: {message}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await self._base_ask(model, messages, json_mode=True)
        return {k: v for k, v in result.items() if isinstance(v, str) and v.strip()}

    async def suggest_tags(self, statement: Dict, model: str) -> list[str]:
        system_prompt = (
            "Ты — эксперт по спортивному программированию. "
            "На основе условия задачи предложи краткие теги (не более 8 штук), "
            "которые точно описывают алгоритмы и техники, необходимые для решения. "
            "Примеры тегов: binary search, dp, greedy, graphs, dfs and similar, "
            "constructive algorithms, implementation, math, sortings, two pointers, "
            "data structures, trees, strings, number theory, geometry, brute force. "
            "Выведи JSON: {\"tags\": [\"tag1\", \"tag2\", ...]}. "
            "Используй теги из стандартного набора Codeforces, только английский язык."
        )
        user_prompt = f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await self._base_ask(model, messages)
        tags = result.get("tags", [])
        return [str(t) for t in tags if t]

    async def generate_samples(
        self, statement: Dict, model: str, count: int = 3
    ) -> list[dict]:
        system_prompt = (
            "Ты — эксперт по задачам спортивного программирования. "
            "Создай небольшие демонстрационные примеры (сэмплы) для задачи. "
            f"Нужно {count} примера. Каждый пример должен быть небольшим (буквально 1–5 строк ввода), "
            "понятным, покрывающим разные случаи: базовый, граничный, неочевидный. "
            "Вычисли правильный ответ для каждого теста. "
            "Выведи JSON: {\"examples\": [{\"input\": \"...\", \"output\": \"...\"}, ...]}"
        )
        user_prompt = f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await self._base_ask(model, messages)
        examples = result.get("examples", [])
        return [{"input": str(e.get("input", "")), "output": str(e.get("output", ""))} for e in examples]

    async def generate_solution_for_tag(
        self, tag: str, name: str, statement: Dict, model: str
    ) -> str:
        tag_descs = {
            "MA": "основное правильное решение (C++)",
            "OK": "альтернативное правильное решение (C++)",
            "WA": "решение с неверной логикой, которое выдаёт WA",
            "TL": "правильное, но медленное решение (O(n²) или хуже), которое выдаёт TL",
            "ML": "решение с избыточным расходом памяти, которое выдаёт ML",
            "RE": "решение, которое вызывает Runtime Error на некоторых тестах",
            "RJ": "отклоняемое решение (явно неверное)",
        }
        desc = tag_descs.get(tag, f"решение с тегом {tag}")
        system_prompt = (
            f"Ты — эксперт по разработке задач для Polygon. "
            f"Напиши {desc} для задачи. "
            "Верни ТОЛЬКО исходный код на C++ без объяснений и markdown."
        )
        user_prompt = f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await self._base_ask(model, messages, json_mode=False)
        return _strip_code_fences(result["text"].strip())

    async def generate_scoring(
        self,
        statement: Dict,
        model: str,
        enable_groups: bool,
        enable_points: bool,
    ) -> str:
        if not enable_groups and not enable_points:
            return ""

        system_prompt = (
            "Ты — автор задач по спортивному программированию. "
            "На основе условия задачи составь раздел Scoring в формате LaTeX-таблицы. "
            "Используй следующий шаблон (подзадача 0 — это всегда тесты из условия без баллов):\n\n"
            r"\begin{center}" "\n"
            r"    \begin{tabular}{ | c | c | c | c | c | }" "\n"
            r"        \hline" "\n"
            r"        \textbf{\scriptsize{Подзадача}} &" "\n"
            r"        \textbf{\scriptsize{Баллы}} &" "\n"
            r"        \textbf{\scriptsize{Дополнительные ограничения}} &" "\n"
            r"        \textbf{\scriptsize{Необходимые подзадачи}} &" "\n"
            r"        \textbf{\scriptsize{Информация о проверке}} \\ \hline" "\n"
            r"        $0$ & -- & тесты из условия & --  & полная        \\ \hline" "\n"
            r"        $1$ & $X$ & ограничение & 0  & первая ошибка \\ \hline" "\n"
            r"        ..." "\n"
            r"    \end{tabular}" "\n"
            r"\end{center}" "\n\n"
            "ТРЕБОВАНИЯ К ПОДЗАДАЧАМ (очень важно!):\n"
            "- Каждая подзадача должна быть алгоритмически осмысленной: её ограничения должны позволять "
            "написать принципиально более простое решение, чем для полной задачи.\n"
            "- Примеры хороших ограничений по типу задачи:\n"
            "  • Строки: 'строка состоит только из символов «a»', 'алфавит из двух символов', "
            "'строка является палиндромом'\n"
            "  • Графы: 'граф является деревом', 'граф является путём', 'граф двудольный'\n"
            "  • Массивы: 'массив отсортирован', 'все элементы различны', 'элементы не превышают $10^3$'\n"
            "  • Числа: 'n является степенью двойки', 'n нечётное', 'все числа простые'\n"
            "- Подзадачи с ограничениями только на n ($n \\le 1000$) допустимы, но должны сочетаться "
            "с содержательными структурными ограничениями.\n"
            "- Подзадачи должны идти от простых к сложным.\n"
            "- Сумма баллов за все подзадачи (кроме 0) должна быть ровно 100.\n"
            "Используй LaTeX для записи ограничений: $n \\le 10^4$, $n \\le 10^5$ и т.д. "
            "Информация о проверке — «полная» или «первая ошибка». "
            "Верни ТОЛЬКО LaTeX-код таблицы, без пояснений, без JSON."
        )
        user_prompt = f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await self._base_ask(model, messages, json_mode=False)
        return result["text"].strip()

    async def generate_interactor(self, statement: Dict, model: str) -> str:
        system_prompt = (
            "Ты — эксперт по задачам с интерактором для Polygon (testlib.h). "
            "Напиши interactor.cpp для интерактивной задачи, используя testlib.h. "
            "Интерактор должен: читать ответы участника, проверять их, выводить подсказки. "
            "Верни ТОЛЬКО исходный код без объяснений и markdown."
        )
        user_prompt = f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await self._base_ask(model, messages, json_mode=False)
        return _strip_code_fences(result["text"].strip())

    async def generate_interaction_text(self, statement: Dict, model: str) -> str:
        """Generates the Interaction section text for an interactive problem statement."""
        system_prompt = (
            "Ты — автор задач по спортивному программированию. "
            "Напиши раздел «Взаимодействие» (Interaction) для интерактивной задачи. "
            "Раздел должен описывать протокол общения между участником и жюри: "
            "что читает программа, что она выводит, как завершается диалог, "
            "сколько запросов допустимо, как жюри отвечает на каждый запрос. "
            "Пиши кратко и ясно, как в условиях Codeforces. "
            "ФОРМАТИРОВАНИЕ — ТОЛЬКО LaTeX: жирный \\textbf{}, курсив \\textit{}, "
            "код \\texttt{}, математика $...$. Никакого Markdown. "
            "Верни ТОЛЬКО текст раздела «Взаимодействие», без заголовка, без JSON."
        )
        user_prompt = f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await self._base_ask(model, messages, json_mode=False)
        return result["text"].strip()

    async def refine_file(
        self,
        file_key: str,
        current_code: str,
        feedback: str,
        statement: Dict,
        model: str,
    ) -> str:
        system_prompt = (
            f"Ты — эксперт по разработке задач для Polygon. "
            f"Пользователь хочет внести правки в файл '{file_key}'. "
            f"Верни ТОЛЬКО исправленный код без объяснений, без markdown блоков."
        )
        user_prompt = (
            f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}\n\n"
            f"Текущий код ({file_key}):\n{current_code}\n\n"
            f"Правки пользователя: {feedback}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await self._base_ask(model, messages, json_mode=False)
        return result["text"].strip()

    # ─────────────────────── Router Agent ───────────────────────────────────────

    async def classify_intent(self, message: str, context: str, model: str) -> str:
        """Router agent: returns 'modify' or 'answer'."""
        context_desc = {
            "statement": "problem statement / description",
            "task": "any code files in the problem",
        }.get(context, f"the {context} source file")

        system = (
            "You classify user intent in a competitive programming problem editor.\n"
            "Return ONLY JSON: {\"intent\": \"modify\" | \"answer\"}\n"
            "- \"modify\": user wants to change, fix, update, rewrite, add or improve something\n"
            "- \"answer\": user asks a question, wants explanation, analysis, or information\n"
            "Be decisive. When in doubt prefer \"answer\"."
        )
        user_msg = f"Context: user is viewing {context_desc}.\nUser message: \"{message}\""
        try:
            result = await self._base_ask(
                model,
                [{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
                json_mode=True,
            )
            intent = result.get("intent", "answer")
            return intent if intent in ("modify", "answer") else "answer"
        except Exception:
            return "answer"

    # ─────────────────────── Answer Agent ───────────────────────────────────────

    async def answer_question(
        self,
        message: str,
        context: str,
        statement: Dict,
        files: Dict,
        model: str,
        history: List[Dict],
    ) -> str:
        """Returns a plain-text answer to the user's question in Russian."""
        ctx_parts: list[str] = []

        if statement:
            stmt_summary = {k: v for k, v in statement.items() if k in ("name", "legend", "input", "output")}
            ctx_parts.append(f"ЗАДАЧА: {json.dumps(stmt_summary, ensure_ascii=False)}")

        if context not in ("statement", "task") and context in files:
            code = files[context]
            ctx_parts.append(f"ФАЙЛ ({context}):\n```\n{code[:3000]}\n```")
        elif files:
            ctx_parts.append(f"Доступные файлы: {', '.join(files.keys())}")

        system = (
            "Ты — эксперт по спортивному программированию и разработке задач для Polygon. "
            "Отвечай на вопросы пользователя чётко, полезно и по-русски. "
            "Не вноси никаких изменений — только отвечай."
        )

        msgs: List[Dict] = [{"role": "system", "content": system}]
        for h in (history or [])[-6:]:
            if isinstance(h, dict) and h.get("role") in ("user", "assistant"):
                msgs.append(h)

        user_content = "\n\n".join(ctx_parts) + f"\n\nВОПРОС: {message}" if ctx_parts else message
        msgs.append({"role": "user", "content": user_content})

        result = await self._base_ask(model, msgs, json_mode=False)
        return result.get("text", "Не удалось получить ответ.").strip()
