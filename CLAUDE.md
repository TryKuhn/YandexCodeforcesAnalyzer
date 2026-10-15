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
- **ИИ-создание задач в Polygon** — отдельный сервис `services/ai-authoring`: чат (вопрос/правка),
  генерация задачи целиком по идее, группы тестов и баллы (генератор на группу, FreeMarker-скрипт,
  COMPLETE_GROUP + first-failed), автосборка пакета с авто-починкой (3 попытки), синхронизация
  с Polygon и уведомления об изменениях. Это самая сложная часть проекта.
- **Экспорт задачи из Polygon в ejudge** (`backend/api/user/ejudge/`): SSH/SFTP + перезагрузка
  конфигурации через веб-интерфейс, группы/баллы → `valuer.cfg` для gvaluer.

---

## 2. Архитектура и стек

Монорепозиторий из двух приложений + БД, всё запускается через Docker Compose.

| Слой      | Технологии |
|-----------|-----------|
| Backend   | Python 3.11, FastAPI, SQLAlchemy (async), Alembic, asyncpg, httpx/aiohttp |
| Frontend  | React 19, Vite, TypeScript, TailwindCSS v4, react-router v7, axios, zustand, CodeMirror, react-markdown + KaTeX |
| БД        | PostgreSQL 15 |
| Плагиат   | C++ (Clang/LLVM), собирается в образ backend через CMake + pybind11 (`plagiarism_cpp*.so`) |
| Judge     | Python 3.11 (stdlib), песочница на **isolate** v2.6, `testlib.h`, отдельный контейнер |
| Прокси    | Caddy (только prod, `Caddyfile`) |
| AI-сервис | `services/ai-authoring`: FastAPI + свой воркер, таблицы `authoring_*` в той же БД |
| LLM       | OpenRouter; Claude Opus 5.5 (по умолчанию), Sonnet 5.5, GPT-6.1 Sol; роутер — Haiku 5.5 (фолбэк Sonnet 5.5) |

### Backend (`backend/`)
- `app/` — `server.py` (сборка FastAPI, middleware, подключение роутеров), `database.py` (async engine/`Session`).
- `api/` — роуты и логика по доменам:
  - `crypt/` — JWT/аутентификация (`get_current_user`).
  - `user/auth/`, `user/codeforces/`, `user/yandex/`, `user/polygon/`, `user/ai/` (прокси в
    AI-сервис), `user/ejudge/`, `user/plagiarism/`, `user/contests.py`, `user/merge_*.py`.
- `models/` — SQLAlchemy-модели по доменам; `models/judge/` — домен своей тестирующей
  системы (problem/test/submission/run + contest/participant): вход/ответ теста и исходник
  посылки — это sha256-ссылки на блобы (см. `blobs/`), одинаковые тесты между задачами
  дедупятся сами. `alembic/` — миграции. `settings.py` — конфиг из `.env` (pydantic-settings).
- `api/judge/` — контесты своей ТС: `contests.py` (CRUD только для Admin, скорборд),
  `scoreboard.py` (ЧИСТЫЕ функции подсчёта ICPC/IOI — вся логика тестируется без БД),
  `cache.py` (кэш таблицы, сбрасывается ПО СОБЫТИЮ — судейство посылки, правка состава задач),
  `submissions.py` (отправка решения и свои посылки), `client.py` (HTTP к judge-сервису),
  `grading.py` (job-хендлер: собрать тесты из блобов → позвать судью → разложить прогоны и
  вердикт → сбросить кэш). **Сквозной поток:** портал → `POST /judge/contests/{id}/submissions`
  → блоб + строка `queued` → job в Redis → воркер (`python -m jobs.run_worker`) → судья →
  `judged` + `JudgeRun` по тестам → скорборд. Судья недоступен → job ретраится, посылка не теряется.
  ICPC: решённые + пенальти `время + 20 мин × неудачные попытки`, CE попыткой не считается,
  попытки после решения бесплатны. IOI: сумма ЛУЧШИХ результатов по задачам, пенальти нет.
- `jobs/` — durable-очередь фоновых задач: строка в таблице `jobs` — источник правды
  (статус/прогресс/результат), Redis Streams только будит воркеров. `enqueue()` → пуш id;
  воркер (`python -m jobs.run_worker`) атомарно забирает job (`UPDATE..RETURNING` — дубли
  доставки безвредны), ретраи с лимитом попыток, брошенные задачи возвращает `XAUTOCLAIM`.
- `blobs/` — контент-адресное хранилище: байты лежат в S3 (в compose — сервис `s3` на RustFS: MinIO убрал публичные образы) под своим sha256
  (`BlobStore.put/get`), строка в таблице `blobs` держит refcount — дедуп бесплатный,
  удалять объект можно только при refcount=0 (сам GC — YCA-210, отдельный тикет).
- `plagiarism/` — исходники C++-модуля. `tests/` — pytest (зеркалит структуру `api/`). `conftest.py`, `pytest.ini`, `mypy.ini`.

Роутеры (`app/server.py`), все кроме health/auth требуют `get_current_user`:
`/api/health`, `/api/auth`, `/api/contests`, `/api/codeforces`, `/api/polygon`,
`/api/ai` (прокси в AI-сервис), `/api/ejudge`, `/api/yandex`, `/api/analytics` (плагиат).

### Frontend (`frontend/src/`)
`App.tsx` (роутинг), `api/` (axios-инстанс, `VITE_API_URL=http://localhost:8000/api`),
`components/`, `constants/`, `pages/`, `store/` (zustand), `utils/`.
Навигация — верхнее меню (без сайдбара). Страница ИИ-задачи: `pages/tasks/` (вкладки условия,
файлов, тестов, пакетов + `ChatPanel`).

### Judge (`backend/judge/`) — своя тестирующая система
**Отдельный сервис со своим контейнером**, лежит внутри `backend/` (общий build context,
благодаря чему делит с бэкендом `testlib.h`). Код НЕ импортируется бэкендом и сам из
бэкенда не импортирует. Эпик «Ф4 Своя ТС» (YCA-400…412). Запускает недоверенный код
участников в песочнице и выдаёт вердикт.

- `app/sandbox/` — песочница: `limits.py` (лимиты), `result.py` (`RunStatus`), `meta.py`
  (разбор meta-файла isolate + классификация), `pool.py` (пул box-id), `base.py`
  (интерфейс `Sandbox`), `isolate.py` (реализация).
- `app/languages/` — реестр языков: `registry.py` (`Language`, C++ `g++ -O2`, Python
  `py_compile` + `tl_multiplier=3`), `compile.py` (компиляция в песочнице, лог компилятора
  обрезается). Новый язык добавляется через `register()` — код судейства не меняется.
- `app/engine/` — движок судейства: `judge.py` (компиляция → прогон по тестам → чекер →
  агрегация), `checker.py` (протокол testlib: вердикт по КОДУ ВОЗВРАТА чекера, а не diff;
  `_fail`=3 → внутренняя ошибка, `_points`=7 → частичные баллы), `scoring.py` (группа платит
  только если прошли ВСЕ её тесты), `spec.py`/`result.py` (входные данные и результаты),
  `verdict.py` (`OK/WA/TLE/MLE/RE/PE/CE/XX`).
- `app/authoring/` — локальная сборка задачи БЕЗ Polygon: `builder.py` (компиляция
  генератора/валидатора/эталона → генерация входов → валидация → ответы прогоном эталона →
  самодостаточный пакет), `lock.py` (блокировка на задачу: локальная и Redlock на Redis —
  два воркера не собирают одну задачу одновременно). Невалидный тест останавливает сборку.
- `app/packaging/` — обмен пакетами через плагины: `native` (свой формат, ничего не теряет)
  и `polygon` (раскладка `problem.xml` + `tests/NN` + `tests/NN.a` + `check.cpp`). Polygon —
  ОДИН ИЗ форматов, а не привилегированный: новый добавляется через `register()`.
  Круговой прогон (собрать → экспорт → импорт → судить) проверяется в CI.
- `app/workers/` — пул воркеров: N asyncio-тасок разбирают очередь прогонов, события
  (queued/started/finished) уходят в `app/hub.py` (EventHub с реплеем последних событий).
- `app/server.py` — FastAPI: `GET /health`, `POST /judge` (судейство посылки),
  `POST /authoring/build` (сборка задачи из исходников жюри, 409 если уже собирается),
  `POST /demo/hello-world?count=N`, `WS /ws/status` (живой поток событий + прогресс).
  Порт **8001**, сервис `judge` в dev-compose (privileged — единственный такой контейнер).
- `oracle/` — набор решений с ИЗВЕСТНЫМИ вердиктами (`<тег>_<имя>.<ext>`, теги
  `ma/ok/wa/tl/ml/re/pe`). Прогоняется скриптом `./scripts/judge/run-oracle.py`;
  расхождение тега и вердикта = красный CI. Правило: неверное решение должно получать
  вердикт ЧЕСТНО (реально медленное/жрущее/падающее), без `assert(false)` и пустых циклов.
- `Dockerfile` — isolate v2.6 из исходников (версия запиннена), `g++`, `python3`.
  Собирается с context `./backend`: `docker build -f backend/judge/Dockerfile backend`.
- Рантайм-зависимости минимальны (fastapi+uvicorn) → тесты гоняются локально без Docker.
- testlib.h берётся общий — `backend/api/user/polygon/archive/assets/testlib.h`.

Почему отдельный контейнер: песочнице нужны привилегии (cgroup v2, namespaces). В своём
контейнере они есть только у judge, а backend с кредами платформ остаётся без них.
Решение «isolate, а не nsjail» и требования к хосту — `docs/judge/host-requirements.md`,
проверка хоста — `scripts/judge/host-probe.sh`.

Линтеры бэкенда judge НЕ проверяют (`backend/ruff.toml`, `exclude` в `backend/mypy.ini`) —
у него свой джоб `judge-test` в CI и свой пакет с именем `app`.

---

## 3. Подсистема ИИ-создания задач (важно, строгие правила)

Три части, строго разделённые — **не нарушать**:

- **`backend/api/user/polygon/`** — ТОЛЬКО вызовы Polygon API и работа с БД. Никакой логики ИИ.
  - `client.py` — ядро: сериализация параметров (`None` не шлётся, `bool`→`true/false`, списки→через запятую),
    подпись (подписываются ВСЕ параметры, бинарь — побайтно), разбор ответа, ретраи 5xx/таймаутов/rate limit
    (кроме `problem.create`/`buildPackage`/`addIssue`/`updateIssue` — их после 5xx не повторяем). Ошибки —
    `PolygonAPIError` (`http_status`, `result`), неверный параметр — `PolygonParamError` (422).
  - `methods/` — по одной функции на КАЖДЫЙ метод API, сигнатура `(problem_id, <обязательные>, user_id, db, *, <необязательные>)`,
    перечислимые значения проверяются по `constants.py`. Новые обёртки — только сюда, через `client.call`.
  - `cache.py` — `refresh_*`: запрос к API + upsert кэша (`PolygonProblem/Statement/Solution`). `methods` в БД не пишут.
  - `problems/`, `contests.py`, `archive/`, `auth/` — HTTP-роуты (`/api/polygon/...`).
- **`services/ai-authoring/`** — ВСЯ логика ИИ, отдельный сервис (контейнеры `ai-authoring` и `ai-worker`).
  С Polygon работает ТОЛЬКО через ручки бэкенда `/api/polygon/*` (`authoring/polygon/client.py`),
  подписывая короткоживущий JWT от имени пользователя (`auth.mint_user_token`, общий `SECRET_KEY`) —
  поэтому фоновая работа (синк, сборки) не зависит от живого запроса. Бэкенд проксирует `/api/ai/*`
  в сервис (`backend/api/user/ai/proxy.py`), фронт ходит на один origin.
  - `llm/models.py` — реестр моделей; `llm/client.py` — единственный клиент OpenRouter (ретраи,
    фолбэк при региональной блокировке, `cache_control` для материалов задачи у Anthropic).
  - `llm/prompts.py` — все промпты; `llm/protocol.py` — **теговый формат ответа** (`<file role=.. name=..>`,
    `<statement field=..>`, `<script>`, `<limits/>`, ...): код и LaTeX берутся дословно, без JSON-экранирования.
    JSON — только для маленьких структур (роутер, план тестов).
  - `sync/` — снимок задачи (инкрементально: содержимое файла перечитывается только при смене mtime/длины),
    дифф снимков → уведомления (`Event`), `dossier.py` — материалы задачи, которые получает КАЖДАЯ модель.
  - `pipeline/` — «прогоны» (`Run`), их выполняет воркер (`runner.py`, по одному на задачу одновременно):
    `chat` (Haiku-роутер → ответ или правки Opus строго в пределах целей), `generate` (задача целиком),
    `groups` (план групп → генераторы, скрипт, группы/баллы, «Система оценки»), `build` (сборка + до 3 починок).
    Прогон с результатом `build: True` автоматически получает следом прогон сборки.
  - `pipeline/groups.py` — план тестов. Скрипт FreeMarker строит КОД, не модель: примеры — ручные тесты 1..k,
    затем строки скрипта по порядку групп, в конце каждой строки уникальный номер. Группы:
    `COMPLETE_GROUP` + `ICPC` (first-failed), зависимости, все баллы группы на ОДНОМ тесте (остальные 0).
  - `api/routes.py` — HTTP (`/api/ai/...`): UI шлёт сообщение/запуск и опрашивает `/sessions/{id}/state`.
- **`backend/api/user/ejudge/`** — экспорт полного пакета Polygon в контест ejudge (job `ejudge.export`
  в общем воркере): `package.py` (разбор `problem.xml`), `convert.py` (каталог задачи, `[problem]`,
  `valuer.cfg`), `servecfg.py` (точечная правка `serve.cfg`), `remote.py` (SSH/SFTP), `web.py` (reload
  через serve-control/new-master), `export.py` (оркестрация), `router.py` (`/api/ejudge/...`).
  `assets/gvaluer.cpp` — валюер из ejudge (GPLv2+, самодостаточный), компилируется в каталоге задачи.

Старый пакет `backend/api/user/gpt/` выведен из использования (роутер не подключён) и подлежит удалению
вместе с `backend/tests/unit/gpt/`; таблица `ai_sessions` (`models/task/session.py`) больше не пишется.

## 4. Запуск проекта (dev)

Всё крутится в Docker. Есть `Makefile` (используй его команды).

```bash
make dev.up            # docker compose -f docker-compose.dev.yml up -d --build
make dev.down
make dev.logs.be       # логи backend;  make dev.logs.fe — логи frontend
make dev.logs.worker   # логи воркера очереди;  make dev.logs.judge — логи судьи
make dev.restart.worker  # воркер БЕЗ авто-релоада: после правок jobs/ и api/judge/grading.py
make dev.restart.ai-worker  # воркер AI-сервиса тоже без авто-релоада
make dev.logs.ai       # логи AI-сервиса и его воркера
make judge.test        # тесты judge локально (+ make judge.lint)
make ai.test           # тесты AI-сервиса локально (+ make ai.lint)
```

Порты и URL:
- Backend API: **http://localhost:8000/api** (uvicorn `--reload`, код примонтирован volume — правки подхватываются).
- Frontend: **http://localhost:5173** (Vite HMR).
- Postgres: **localhost:5432**.
- AI-сервис: **http://localhost:8100/api/ai** (напрямую; фронт ходит через прокси бэкенда).

Контейнеры: `yandexcodeforcesanalyzer-backend-1`, `-worker-1`, `-ai-authoring-1`, `-ai-worker-1`, `-judge-1`, `-frontend-1`,
`-frontend-participant-1`, `-postgres-1`, `-redis-1`, `-s3-1`.
`worker` — тот же образ backend с командой `python -m jobs.run_worker`; без него посылки
навсегда остаются `queued`.
Миграции применяются автоматически при старте backend (`alembic upgrade head` в CMD); у AI-сервиса
свои миграции (`services/ai-authoring/alembic`, таблица версий `alembic_version_ai_authoring`),
они применяются при старте контейнера `ai-authoring`. Без `ai-worker` сообщения в чате навсегда «в очереди».

### `.env` (корень репозитория) — НЕОЧЕВИДНО
`.env` пробрасывается в контейнеры через `env_file:` в compose. Значит:
- **`docker restart` НЕ перечитывает `.env`.** После правки `.env` нужно пересоздать сервис:
  `docker compose -f docker-compose.dev.yml up -d backend`.
- Новые Python-файлы/правки `.py` подхватываются авто-релоадом uvicorn без пересоздания.
- Ключевые переменные: `OPENAI_API_KEY` (OpenRouter, нужен AI-сервису), `SECRET_KEY` (общий для бэкенда и AI-сервиса), `POSTGRES_*`,
  Yandex/CF client id/secret; опционально `LLM_MAX_TOKENS`, `OPENROUTER_PROVIDER_ORDER/IGNORE/ALLOW_FALLBACKS`,
  `REDIS_HOST`/`REDIS_PORT` (дефолты `redis`/6379 подходят для compose).

- AI-сервис: `SYNC_INTERVAL_MINUTES` (5), `SYNC_ACTIVE_WINDOW_HOURS` (24), `LLM_MAX_TOKENS` (32000),
  `MAX_REPAIR_ATTEMPTS` (3), `BUILD_TIMEOUT_SECONDS`; бэкенд: `AI_SERVICE_URL`, `AI_DEFAULT_MODEL`.
- Экспорт в ejudge (необязательно): `EJUDGE_SSH_HOST/PORT/USER`, ключ и `known_hosts` в `./secrets/ejudge/`
  (монтируется в backend/worker как `/run/secrets/ejudge`), `EJUDGE_JUDGES_DIR`, `EJUDGE_URL/LOGIN/PASSWORD`
  (для reload), `EJUDGE_GVALUER_PATH` (готовый gvaluer на хосте — иначе компилируем свой).

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
docker exec yandexcodeforcesanalyzer-backend-1 sh -c "cd /app && python -m pytest tests/unit/ejudge -q"
```

- `pytest.ini`: `testpaths=tests`, `asyncio_mode=auto`. Тесты зеркалят `api/` (папка `tests/unit/...`).
  Есть переопределённый `norecursedirs`, чтобы собирался пакет `.../build` (иначе pytest его пропускает).
- Фикстуры (`conftest.py`): async `db`, `user`, `polygon_api` (фейковый транспорт Polygon) и т.п. LLM в тестах всегда мокается.
- Набор большой (~1000+ тестов), должен быть полностью зелёным.

AI-сервис тестируется локально, без Docker и внешних сервисов (sqlite + фейковые backend/LLM в
`services/ai-authoring/tests/fakes.py`): `cd services/ai-authoring && pytest -q` (или `make ai.test`).
`FakeBackend` моделирует Polygon (скрипт FreeMarker, группы, пакеты), `FakeLLM` отвечает по маркерам промптов.

Фронтенд отдельного тест-раннера не имеет — гейт качества там это type-check (`tsc`, см. ниже).

### Тесты judge (`backend/judge/`) — без Docker
У judge нет рантайм-зависимостей (только stdlib), поэтому его тесты гоняются локально:

```bash
cd backend/judge
pip install -r requirements-dev.txt
pytest -q                            # meta-парсер, лимиты, пул box-id, языки, компиляция
ruff check .
mypy app --ignore-missing-imports
```

Покрывается логика, НЕ требующая isolate (разбор meta, классификация вердиктов, пул).
Сама песочница требует привилегированного хоста с cgroup v2 и проверяется вручную.
В CI это джоб `judge-test` (фильтр `backend/judge/**`); бэкендовые джобы judge исключают.

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
  **Тесты удалять МОЖНО:** `problem.deleteTest` (обёртка `polygon.methods.delete_tests`). Он
  атомарный: если хоть один тест не проходит пред-проверку (например, сгенерирован скриптом) — не удаляет ничего.
- **Некорректные решения (WA/TL/ML/RE) должны ЧЕСТНО получать свой вердикт настоящим алгоритмом.**
  Никаких бесконечных циклов / `assert(false)` / искусственных задержек. Если гарантировать вердикт
  нельзя — генератор возвращает `SKIP: причина`, решение не грузится, причина показывается пользователю.
- **Кириллица в исходниках.** В коде (комментарии/литералы) — только ASCII: Polygon хранит файлы в
  cp1251, UTF-8-кириллица ломает кодировку. Также: не редактируй исходники PowerShell-текстовыми
  cmdlet'ами (`Set-Content`/`Out-File`) — UTF-8-кириллица манглится; используй инструменты редактирования.
- **Время сервера — наивный UTC** (без tz). На фронте всегда парси через `parseServerDate`, иначе время «плывёт».
- **`problem.saveTest`: `testInput` опционален** — можно обновить только `testPoints`/`testGroup`
  существующего (в т.ч. сгенерированного скриптом) теста по индексу, вход слать не нужно.
- **Две alembic-цепочки в одной БД.** Бэкенд и AI-сервис мигрируют независимо (разные таблицы версий).
  `backend/alembic/env.py` фильтрует чужие таблицы (`authoring_*`) — без фильтра автогенерация бэкенда
  предлагает их ДРОПНУТЬ. Сервис, наоборот, видит только `authoring_*`.
- **AI-сервис ходит в Polygon только через бэкенд.** Ключи Polygon и подпись живут в бэкенде; сервис
  подписывает JWT пользователя сам (claim `svc=ai-authoring`). Сменили `SECRET_KEY` — меняйте в обоих.
- **Прогоны одной задачи не пересекаются**, а синхронизация пропускается, пока идёт прогон (иначе
  собственные правки ИИ показались бы пользователю «изменениями в Polygon»). Воркер AI — один экземпляр.
- **Ответы моделей — теговый протокол, а не JSON.** Код с кавычками/бэкслешами в JSON ломается.
  `#include <testlib.h>` нормализуется в `"testlib.h"` (иначе Polygon не находит testlib).
- **Правка вне целей отбрасывается.** Роутер даёт минимальный набор целей; `apply_edits(allowed=...)`
  отбрасывает остальное и показывает это пользователю («Не применено (вне запроса)»).
- **Экспорт в ejudge требует `advanced_layout`** в контесте и ПОЛНОГО пакета (с тестами и ответами;
  качаем `linux`, фолбэк `windows`/`standard`). gvaluer читает `valuer.cfg` из СВОЕГО каталога, поэтому
  он компилируется в каталог каждой задачи; группы должны идти подряд — тесты перенумеровываются.
- **LaTeX в условиях** — ограниченный набор команд Polygon (код через `lstlisting`, не `verbatim`).
- **CI ничего не проверяет, если не тронуты нужные пути.** В `ci.yml` стоит `dorny/paths-filter`:
  джобы бэка/фронта/judge запускаются только при изменениях в `backend/**`, `frontend/**`,
  `judge/**`. PR, трогающий только `docs/` или `scripts/`, получает зелёную галку, НЕ прогнав
  ни одного теста. Зелёный CI ≠ протестировано.
- **`testlib.h` лежал не там.** Файл был закоммичен в `frontend/backend/api/user/polygon/archive/assets/`
  (вся эта папка — артефакт запуска команды не из того каталога), хотя `uploader.py:38` ищет его
  рядом с собой. Из-за этого догрузка testlib при импорте архива падала. Файл перемещён на
  ожидаемый путь и теперь ОДИН на весь репозиторий — его же берёт judge-образ.
- **Judge не импортирует из `backend/`, и наоборот.** Лежит внутри `backend/` только ради общего
  build context; логически это отдельный сервис со своим контейнером и своими линтерами.
- **`ruff` в бэкенде запиннен (`ruff==0.14.0`).** Раньше стояло `>=0.9.0`, и свежие версии
  добавили правил на 700+ срабатываний в существующем коде — CI бы покраснел на ровном месте.
  Поднимать версию можно только вместе с разгребанием этих ошибок.
- **Вердикт MLE легко спутать с RE.** При превышении памяти процесс убивает SIGKILL, то есть
  выглядит как сигнал. В `meta.classify` память проверяется ДО сигналов — иначе каждый MLE
  превращается в RE. Тот же порядок обязателен в любой новой логике вердиктов.
- **`cg-mem` нельзя использовать как признак MLE.** Это пик памяти по всей cgroup, а box
  делится с компилятором: после `g++` там остаётся ~227 МБ, и любой прогон становился ложным
  MLE. MLE даёт ТОЛЬКО флаг `cg-oom-killed`, в отчёт идёт `max-rss` (пик самого процесса).
- **isolate вызывает `execve(argv[0])` и НЕ ищет по `PATH`** — компиляторы/интерпретаторы
  в реестре языков указаны абсолютными путями (`/usr/bin/g++`), иначе `No such file`.
- **isolate в контейнере требует ручной подготовки** (обычно это делает systemd): свой
  `judge/isolate.cf` (без `subid_user`, с явным диапазоном UID) и `judge/entrypoint.sh`
  (создать `/run/isolate/locks`, увести процессы в `/sys/fs/cgroup/init`, включить контроллеры
  в корне И в `/sys/fs/cgroup/isolate`). Устанавливать isolate через `make install`, а не
  копированием бинарей: `default.cf` генерируется при сборке.
- **Реальную проверку судейства делает CI-джоб `judge-e2e`**, а не dev-машина: там нужен
  cgroup v2 + привилегии. Он собирает образ и гоняет `scripts/judge/demo-judge.py` — пять
  решений A+B должны получить OK/WA/TLE/MLE/RE. Это главный гейт честности вердиктов.

---

## 10. Прочее

- `make dev.migrate msg="..."` — автогенерация миграции; `make dev.migrate.upgrade/downgrade`.
- `make dev.db.shell` — psql в контейнере. `make dev.clean` — снести всё (образы/volume).
- Prod: `docker-compose.prod.yml` + Caddy; команды `make prod.*`. Локальная разработка — только `dev.*`.
- **Автодеплой** (`.github/workflows/cd.yml`): после зелёного CI на `main` собираются только
  изменившиеся образы (`backend`, `ai-authoring`, `frontend`, `frontend-participant`, `judge`), а неизменённые
  получают тег коммита ретегом `:latest` без пересборки — весь стек всегда на одном `IMAGE_TAG`.
  Деплой ждёт здоровья `backend`, `judge`, `worker`, `ai-authoring` и `ai-worker`, иначе откатывает все app-сервисы на
  предыдущий тег. Caddyfile подхватывается через `caddy reload` (`make prod.caddy.reload`).
- Память Claude по проекту (кросс-сессионная) лежит в `~/.claude/projects/.../memory/` — там же
  детальные заметки по подсистеме ИИ-задач и подводным камням.
