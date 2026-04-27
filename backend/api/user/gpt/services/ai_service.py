import json
import logging
import re
from typing import Dict, List

import httpx
from fastapi import HTTPException

from settings import settings

logger = logging.getLogger(__name__)


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
        payload = {
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
            except Exception as e:
                logger.error(f"AI Service Exception: {str(e)}")
                raise

    async def generate_statement(
        self, user_idea: str, model: str, user_prompt: str, history: List[Dict]
    ) -> Dict:
        system_prompt = (
            "Вы — автор задач по спортивному программированию. "
            "ПРАВИЛО: Пишите условия максимально простым и понятным языком, доступным школьнику. "
            "Избегайте излишней математической терминологии, если это возможно. "
            "Используйте LaTeX для формул. Выводите ТОЛЬКО JSON: "
            "{name, legend, input, output, notes, tutorial}."
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
            "https://codeforces.com/blog/entry/18431 (статья о чекерах), "
            "На основе условия задачи создай технические файлы для Polygon. "
            "Нужно сгенерировать: validator.cpp, generator.cpp, checker.cpp, "
            "solution.cpp (Main), а также решения с тегами: "
            "WA (Wrong Answer), TL (Time Limit Exceeded), RE (Runtime Error), ML (Memory Limit). "
            "Выведи JSON: {validator, generator, checker, solution_py, solution_cpp,"
            "wa_sol, tl_sol, re_sol, ml_sol, script}."
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
        return await self._base_ask(model, messages)

    async def fix_code(
        self, error: str, component: str, code: str, statement: Dict, model: str
    ) -> str:
        system_prompt = f"Fix the {component} code for Polygon. Error: {error}. Return only the corrected code, no explanations."
        user_prompt = f"Statement:\n{json.dumps(statement, ensure_ascii=False)}\n\nBroken code:\n{code}"
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
        """Правка конкретного файла по отзыву пользователя"""
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
