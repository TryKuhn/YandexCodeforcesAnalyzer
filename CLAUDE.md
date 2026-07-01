# CLAUDE.md

Гид для Claude Code (и людей) по этому репозиторию. Читай целиком перед изменениями.

---

## 1. Что это за проект

**YandexCodeforcesAnalyzer** — веб-приложение для курса «Алгоритмы и структуры данных»
(2 курс ПИ ВШЭ). Помогает преподавателю/жюри работать с системами тестирования
**Яндекс.Контест**, **Codeforces** и **Polygon**. Основные возможности:

- Авторизация, подключение аккаунтов Яндекс/CF/Polygon, выгрузка посылок и результатов контестов.
- Просмотр посылок с фильтрами (участник, задача, время, вердикт), аналитика решаемости, графики.
- Поиск подозрительной активности (спам-посылки, синхронная отправка с разных аккаунтов).
- Пересчёт локальных рейтингов, пометки/раскраска участников.
- **Проверка решений на плагиат** (нативный C++-модуль на Clang/LLVM через pybind11).
- **Проверка решений на схожесть с ИИ**.
- **ИИ-создание задач в Polygon** — крупная подсистема: чат-агент генерирует условие,
  файлы (валидатор/генератор/чекер/интерактор/скорер/решения/скрипт тестов), настраивает
  группы и баллы, собирает пакет и авто-чинит ошибки сборки. Это самая сложная часть проекта.

---

## 2. Архитектура и стек

Монорепозиторий из двух приложений + БД, всё запускается через Docker Compose.

| Слой      | Технологии |
|-----------|-----------|
| Backend   | Python 3.11, FastAPI, SQLAlchemy (async), Alembic, asyncpg, httpx/aiohttp |
| Frontend  | React 19, Vite, TypeScript, TailwindCSS v4, react-router v7, axios, zustand, CodeMirror, react-markdown + KaTeX |
| БД        | PostgreSQL 15 |
| Плагиат   | C++ (Clang/LLVM), собирается в образ backend через CMake + pybind11 (`plagiarism_cpp*.so`) |
| Прокси    | Caddy (только prod, `Caddyfile`) |
| LLM       | OpenRouter (`settings.OPENAI_HOST`); модели Claude/Gemini/GPT |

### Backend (`backend/`)
- `app/` — `server.py` (сборка FastAPI, middleware, подключение роутеров), `database.py` (async engine/`Session`).
- `api/` — роуты и логика по доменам:
  - `crypt/` — JWT/аутентификация (`get_current_user`).
  - `user/auth/`, `user/codeforces/`, `user/yandex/`, `user/polygon/`, `user/gpt/`,
    `user/plagiarism/`, `user/contests.py`, `user/merge_*.py`.
- `models/` — SQLAlchemy-модели. `alembic/` — миграции. `settings.py` — конфиг из `.env` (pydantic-settings).
- `plagiarism/` — исходники C++-модуля. `tests/` — pytest (зеркалит структуру `api/`). `conftest.py`, `pytest.ini`, `mypy.ini`.

Роутеры (`app/server.py`), все кроме health/auth требуют `get_current_user`:
`/api/health`, `/api/auth`, `/api/contests`, `/api/codeforces`, `/api/polygon`,
`/api/ai` (gpt), `/api/yandex`, `/api/analytics` (плагиат).

### Frontend (`frontend/src/`)
`App.tsx` (роутинг), `api/` (axios-инстанс, `VITE_API_URL=http://localhost:8000/api`),
`components/`, `constants/`, `pages/`, `store/` (zustand), `utils/`.
Навигация — верхнее меню (без сайдбара). Страница ИИ-задачи: `pages/tasks/` (вкладки условия,
файлов, тестов, пакетов + `ChatPanel`).

---

## 3. Подсистема ИИ-создания задач (важно, строгие правила)

Строгое разделение слоёв — **не нарушать**:
- **`backend/api/user/polygon/`** — ТОЛЬКО вызовы Polygon API и работа с БД. Никакой логики ИИ.
- **`backend/api/user/gpt/`** — ВСЯ логика ИИ. Внутри слои:
  - `services/llm/` — единственный низкоуровневый клиент OpenRouter (`client.ask`/`ask_text`) + реестр моделей.
  - `services/prompts/` — по одному промпту на тип файла.
  - `services/generation/` — генерация условия и файлов (`file_gen.generate_pack` и др.).
  - `services/chat/` — чат-агент: `intent_router` (классификатор действия), `context_resolver`,
    `modify_executor`, `answer_executor`, `file_context`.
  - `services/sync/` — синхронизация сгенерированного в Polygon (через `polygon/`-обёртки).
  - `services/build/` — сборка пакета и авто-починка (`package_loop`, `fix_gen`, `error_parser`, `scoring_groups`).
  - `routes/` — по ОДНОМУ эндпоинту на файл; регистрируются на `gpt_router` (`base_gpt`).

Соглашения: `gpt/` может импортировать `polygon/`-обёртки (это разрешено), но не наоборот.
Один тип файла = один промпт = один генератор.

---

## 4. Запуск проекта (dev)

Всё крутится в Docker. Есть `Makefile` (используй его команды).

```bash
make dev.up            # docker compose -f docker-compose.dev.yml up -d --build
make dev.down
make dev.logs.be       # логи backend;  make dev.logs.fe — логи frontend
```

Порты и URL:
- Backend API: **http://localhost:8000/api** (uvicorn `--reload`, код примонтирован volume — правки подхватываются).
- Frontend: **http://localhost:5173** (Vite HMR).
- Postgres: **localhost:5432**.

Контейнеры: `yandexcodeforcesanalyzer-backend-1`, `-frontend-1`, `-postgres-1`.
Миграции применяются автоматически при старте backend (`alembic upgrade head` в CMD).

### `.env` (корень репозитория) — НЕОЧЕВИДНО
`.env` пробрасывается в контейнеры через `env_file:` в compose. Значит:
- **`docker restart` НЕ перечитывает `.env`.** После правки `.env` нужно пересоздать сервис:
  `docker compose -f docker-compose.dev.yml up -d backend`.
- Новые Python-файлы/правки `.py` подхватываются авто-релоадом uvicorn без пересоздания.
- Ключевые переменные: `OPENAI_API_KEY` (OpenRouter), `SECRET_KEY`, `POSTGRES_*`,
  Yandex/CF client id/secret; опционально `LLM_MAX_TOKENS`, `OPENROUTER_PROVIDER_ORDER/IGNORE/ALLOW_FALLBACKS`.

### Windows-нюанс
Node/npm не в PATH. Вызывай явно: `& "C:\Program Files\nodejs\npx.cmd"` / `npm.cmd`.

---

## 5. Тесты

Бэкенд-тесты запускаются **внутри контейнера backend** (там зависимости и собранный `plagiarism_cpp`).

```bash
make dev.test
# = docker compose -f docker-compose.dev.yml exec backend pytest -q --tb=short

# напрямую (весь набор):
docker exec yandexcodeforcesanalyzer-backend-1 python -m pytest -q

# один файл / каталог:
docker exec yandexcodeforcesanalyzer-backend-1 sh -c "cd /app && python -m pytest tests/unit/gpt/services/build -q"
```

- `pytest.ini`: `testpaths=tests`, `asyncio_mode=auto`. Тесты зеркалят `api/` (папка `tests/unit/...`).
  Есть переопределённый `norecursedirs`, чтобы собирался пакет `.../build` (иначе pytest его пропускает).
- Фикстуры (`conftest.py`): async `db`, `user`, `task_session`, `stub_llm` и т.п. LLM в тестах всегда мокается.
- Набор большой (~1000+ тестов), должен быть полностью зелёным.

Фронтенд отдельного тест-раннера не имеет — гейт качества там это type-check (`tsc`, см. ниже).

---

## 6. Линтеры и проверка типов

### Backend
```bash
make dev.lint       # ruff check .  +  mypy . --ignore-missing-imports --explicit-package-bases
make dev.lint.fix   # black .  +  isort .  +  ruff check . --fix
```
`ruff` на данный момент проходит чисто — держи так.

### Frontend
```bash
# ТИП-ЧЕК (обязательный гейт):
& "C:\Program Files\nodejs\npx.cmd" tsc --noEmit      # запускать из папке frontend/
# либо полная сборка: npm run build  (= tsc -b && vite build)

# eslint:
& "C:\Program Files\nodejs\npm.cmd" run lint
```
⚠️ `npm run lint` сейчас НЕ полностью зелёный: в кодовой базе много `catch (e: any)`
(`@typescript-eslint/no-explicit-any`) и предупреждений `react-hooks/exhaustive-deps` —
это сложившийся стиль проекта. **Не добавляй новых нарушений**, но обязательный гейт для
фронтенда — это чистый `tsc --noEmit`.

---

## 7. Обязательный порядок при любых правках

После КАЖДОГО изменения (перед тем как считать задачу выполненной) проверяй **три вещи**:

1. **Тесты.** Затронул backend → прогони релевантные тесты, а лучше весь набор
   (`make dev.test`). Изменил сигнатуру/контракт — обнови и тесты (они часть кода).
2. **Линтер / типы.** Backend: `make dev.lint` (как минимум `ruff`). Frontend: `tsc --noEmit`
   должен быть чистым; не плоди новых eslint-ошибок.
3. **Запуск.** Убедись, что приложение реально поднимается: backend перезагрузился без ошибок
   (`make dev.logs.be`, ищи `Application startup complete` и отсутствие traceback), нужный
   эндпоинт отвечает (например `curl` → 401/200, а не 404/500), frontend собирается.

Правки в Polygon/OpenRouter, требующие живого аккаунта, честно помечай как непроверенные
в рантайме (в песочнице нет кредов) и предлагай пользователю smoke-тест.

---

## 8. Принципы кода (важно)

- **Пиши максимально простую и понятную реализацию.** Из двух рабочих вариантов выбирай тот,
  что легче читать. Избегай преждевременных абстракций и «умного» кода.
- **Упрощай неочевидное.** Когда трогаешь запутанный участок — по возможности приводи его к более
  простому и прозрачному виду (в разумных рамках правки, без разрастания диффа).
- **Совпадай со стилем окружения** — плотность комментариев, именование, идиомы как в соседнем коде.
- Комментируй ПОЧЕМУ, а не ЧТО. Комментарий уместен там, где логика неочевидна или есть подводный камень.

---

## 9. Подводные камни (проверено, не наступай снова)

- **`problem.packages` НЕ отсортирован от старых к новым.** Нельзя брать `packages[-1]` как
  «только что собранный пакет». Находи новый пакет по `id` (снимок id до сборки → новый = не из снимка).
  Иначе баннер ошибки сборки показывает чужую/устаревшую ошибку.
- **OpenRouter `max_tokens`.** Без явного `max_tokens` OpenRouter резервирует полный вывод модели
  (напр. 65536 у gpt-5.5) и падает pre-flight'ом по балансу (402 «requires more credits»,
  `provider_name: null` — это НЕ причина). Всегда шлём `settings.LLM_MAX_TOKENS`.
- **Региональная блокировка провайдера (403 `unsupported_country_region_territory`).** У некоторых
  моделей единственный провайдер гео-блокирует регион аккаунта — это не баг кода. Обходится
  провайдер-роутингом (`settings.openrouter_provider` → `payload["provider"]`, env
  `OPENROUTER_PROVIDER_IGNORE=OpenAI` и т.п.). Ошибки LLM превращаются в понятный текст в `_friendly_error`.
- **Polygon API НЕ умеет удалять** решения/файлы (только add/edit/view). Удаление — только в веб-интерфейсе Polygon.
- **Некорректные решения (WA/TL/ML/RE) должны ЧЕСТНО получать свой вердикт настоящим алгоритмом.**
  Никаких бесконечных циклов / `assert(false)` / искусственных задержек. Если гарантировать вердикт
  нельзя — генератор возвращает `SKIP: причина`, решение не грузится, причина показывается пользователю.
- **Кириллица в исходниках.** В коде (комментарии/литералы) — только ASCII: Polygon хранит файлы в
  cp1251, UTF-8-кириллица ломает кодировку. Также: не редактируй исходники PowerShell-текстовыми
  cmdlet'ами (`Set-Content`/`Out-File`) — UTF-8-кириллица манглится; используй инструменты редактирования.
- **Время сервера — наивный UTC** (без tz). На фронте всегда парси через `parseServerDate`, иначе время «плывёт».
- **`problem.saveTest`: `testInput` опционален** — можно обновить только `testPoints`/`testGroup`
  существующего (в т.ч. сгенерированного скриптом) теста по индексу, вход слать не нужно.
- **Два поля диалога в сессии:** `session.chat_log` (UI-транскрипт) и `session.history`
  (сообщения для генерации). Не путать — унифицированный чат читает контекст из `chat_log`.
- **LaTeX в условиях** — ограниченный набор команд Polygon (код через `lstlisting`, не `verbatim`).

---

## 10. Прочее

- `make dev.migrate msg="..."` — автогенерация миграции; `make dev.migrate.upgrade/downgrade`.
- `make dev.db.shell` — psql в контейнере. `make dev.clean` — снести всё (образы/volume).
- Prod: `docker-compose.prod.yml` + Caddy; команды `make prod.*`. Локальная разработка — только `dev.*`.
- Память Claude по проекту (кросс-сессионная) лежит в `~/.claude/projects/.../memory/` — там же
  детальные заметки по подсистеме ИИ-задач и подводным камням.
