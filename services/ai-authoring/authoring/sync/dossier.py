"""The problem materials every model gets: statement, limits, sources, tests, groups."""
from __future__ import annotations

from collections import defaultdict

from authoring.sync.diff import STATEMENT_LABELS
from authoring.sync.snapshot import file_role

MAX_FILE_CHARS = 60_000
_LANG_BY_EXT = {"cpp": "cpp", "cc": "cpp", "h": "cpp", "hpp": "cpp", "py": "python", "java": "java", "pas": "pascal"}


def _fence(name: str, content: str) -> str:
    lang = _LANG_BY_EXT.get(name.rsplit(".", 1)[-1].lower(), "")
    if len(content) > MAX_FILE_CHARS:
        content = content[:MAX_FILE_CHARS] + "\n... [обрезано]"
    return f"```{lang}\n{content.rstrip()}\n```"


def _ranges(indices: list[int]) -> str:
    """[1,2,3,5] -> '1-3, 5'."""
    spans: list[list[int]] = []
    for i in sorted(indices):
        if spans and spans[-1][1] == i - 1:
            spans[-1][1] = i
        else:
            spans.append([i, i])
    return ", ".join(f"{a}-{b}" if a != b else f"{a}" for a, b in spans)


def tests_summary(snapshot: dict) -> str:
    tests = snapshot.get("tests") or []
    if not tests:
        return "Тестов нет."
    lines = [f"Всего тестов: {len(tests)}."]
    manual = [t["index"] for t in tests if t.get("manual")]
    generated = [t["index"] for t in tests if not t.get("manual")]
    samples = [t["index"] for t in tests if t.get("useInStatements")]
    if manual:
        lines.append(f"Ручные: {_ranges(manual)}.")
    if generated:
        lines.append(f"Из скрипта: {_ranges(generated)}.")
    if samples:
        lines.append(f"Примеры в условии: {_ranges(samples)}.")
    by_group: dict[str, list[dict]] = defaultdict(list)
    for t in tests:
        if t.get("group") is not None:
            by_group[str(t["group"])].append(t)
    if by_group:
        lines.append("Тесты по группам (номера тестов; сумма баллов):")
        for group, rows in sorted(by_group.items(), key=lambda kv: (len(kv[0]), kv[0])):
            points = sum(float(t.get("points") or 0) for t in rows)
            lines.append(f"- группа {group}: {_ranges([t['index'] for t in rows])}; баллы {points:g}")
    elif any(t.get("points") for t in tests):
        total = sum(float(t.get("points") or 0) for t in tests)
        lines.append(f"Баллы по тестам, сумма {total:g}.")
    return "\n".join(lines)


def build_dossier(snapshot: dict, *, polygon_id: int, problem_type: str) -> str:
    """Render a snapshot as the materials text (Markdown)."""
    info = snapshot.get("info") or {}
    parts: list[str] = [f"# Задача Polygon #{polygon_id}"]

    parts.append(
        "## Параметры\n"
        f"- тип задачи: {problem_type}\n"
        f"- TL: {info.get('timeLimit')} мс, ML: {info.get('memoryLimit')} МБ\n"
        f"- ввод: {info.get('inputFile') or 'stdin'}, вывод: {info.get('outputFile') or 'stdout'}\n"
        f"- интерактивная: {'да' if info.get('interactive') else 'нет'}\n"
        f"- теги: {', '.join(snapshot.get('tags') or []) or '—'}\n"
        f"- чекер: {snapshot.get('checker') or '—'}; валидатор: {snapshot.get('validator') or '—'}; "
        f"интерактор: {snapshot.get('interactor') or '—'}"
    )

    statements = snapshot.get("statements") or {}
    if not statements:
        parts.append("## Условие\nУсловия пока нет.")
    for lang, st in statements.items():
        block = [f"## Условие ({lang})"]
        for field, label in STATEMENT_LABELS.items():
            value = (st.get(field) or "").strip()
            if value:
                block.append(f"### {label} [{field}]\n{value}")
        parts.append("\n\n".join(block))

    samples = snapshot.get("samples") or {}
    if samples:
        block = ["## Примеры (входные данные тестов из условия)"]
        for index, text in sorted(samples.items(), key=lambda kv: int(kv[0])):
            block.append(f"### тест {index}\n```\n{text.rstrip()}\n```")
        parts.append("\n\n".join(block))

    parts.append("## Тесты\n" + tests_summary(snapshot))

    groups = snapshot.get("groups") or []
    if groups:
        rows = [
            f"- {g.get('name')}: points-policy {g.get('pointsPolicy')}, feedback {g.get('feedbackPolicy')}, "
            f"зависит от: {', '.join(g.get('dependencies') or []) or '—'}"
            for g in groups
        ]
        parts.append("## Группы тестов\n" + "\n".join(rows))

    script = (snapshot.get("script") or "").strip()
    parts.append("## Скрипт генерации тестов (FreeMarker)\n" + (f"```\n{script}\n```" if script else "Скрипта нет."))

    files = snapshot.get("files") or {}
    source_blocks: list[str] = []
    other: list[str] = []
    for key in sorted(files):
        entry = files[key]
        role = file_role(snapshot, entry)
        if entry.get("content") is None:
            other.append(f"{entry['name']} ({entry.get('type')}, {entry.get('skipped') or 'не загружен'})")
            continue
        header = f"### {entry['name']} — {role} ({entry.get('type')})\n"
        source_blocks.append(header + _fence(entry["name"], entry["content"]))
    if source_blocks:
        parts.append("## Файлы задачи\n\n" + "\n\n".join(source_blocks))
    if other:
        parts.append("Прочие файлы без содержимого: " + ", ".join(other))

    solutions = snapshot.get("solutions") or {}
    if solutions:
        blocks = []
        for name in sorted(solutions, key=lambda n: (solutions[n].get("tag") != "MA", n)):
            entry = solutions[name]
            if entry.get("content") is None:
                blocks.append(f"### {name} [{entry.get('tag')}] — содержимое не загружено")
            else:
                blocks.append(f"### {name} [{entry.get('tag')}]\n" + _fence(name, entry["content"]))
        parts.append("## Решения\n\n" + "\n\n".join(blocks))
    else:
        parts.append("## Решения\nРешений нет.")

    packages = snapshot.get("packages") or []
    if packages:
        rows = []
        for p in packages[:3]:
            comment = (p.get("comment") or "").strip().replace("\n", " ")
            tail = f": {comment[:500]}" if comment else ""
            rows.append(f"- #{p['id']} rev.{p.get('revision')} {p.get('state')}{tail}")
        parts.append("## Последние пакеты\n" + "\n".join(rows))

    return "\n\n".join(parts)
