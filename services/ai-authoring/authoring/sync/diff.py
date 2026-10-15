"""Human-readable differences between two snapshots (what the user is told)."""
from __future__ import annotations

from collections import Counter

from authoring.sync.snapshot import file_role

ROLE_LABELS = {
    "checker": "чекер",
    "validator": "валидатор",
    "interactor": "интерактор",
    "generator": "генератор",
    "source": "исходник",
    "resource": "ресурс",
    "aux": "вспомогательный файл",
}
INFO_LABELS = {
    "timeLimit": ("TL", " мс"),
    "memoryLimit": ("ML", " МБ"),
    "inputFile": ("входной файл", ""),
    "outputFile": ("выходной файл", ""),
    "interactive": ("интерактивность", ""),
}
STATEMENT_LABELS = {
    "name": "название",
    "legend": "легенда",
    "input": "формат ввода",
    "output": "формат вывода",
    "scoring": "система оценки",
    "interaction": "протокол взаимодействия",
    "notes": "примечание",
    "tutorial": "разбор",
}
PACKAGE_STATES = {"READY": "собран", "FAILED": "ошибка сборки", "RUNNING": "собирается", "PENDING": "в очереди"}


def _change(kind: str, text: str, **extra: object) -> dict:
    return {"kind": kind, "text": text, **extra}


def _file_changed(old: dict, new: dict) -> bool:
    if old.get("mtime") != new.get("mtime") or old.get("length") != new.get("length"):
        if old.get("content") is not None and new.get("content") is not None:
            return old["content"] != new["content"]
        return True
    return False


def diff(old: dict, new: dict) -> list[dict]:
    """Changes from ``old`` to ``new``; empty when nothing user-visible changed."""
    changes: list[dict] = []

    old_info, new_info = old.get("info") or {}, new.get("info") or {}
    for key, (label, unit) in INFO_LABELS.items():
        if key in old_info and key in new_info and old_info[key] != new_info[key]:
            changes.append(_change("info", f"{label}: {old_info[key]}{unit} → {new_info[key]}{unit}"))

    old_st, new_st = old.get("statements") or {}, new.get("statements") or {}
    for lang in sorted(set(old_st) | set(new_st)):
        if lang not in old_st:
            changes.append(_change("statement", f"добавлено условие ({lang})"))
            continue
        if lang not in new_st:
            changes.append(_change("statement", f"удалено условие ({lang})"))
            continue
        fields = [
            STATEMENT_LABELS[f]
            for f in STATEMENT_LABELS
            if (old_st[lang].get(f) or "") != (new_st[lang].get(f) or "")
        ]
        if fields:
            changes.append(_change("statement", f"условие ({lang}): {', '.join(fields)}"))

    if sorted(old.get("tags") or []) != sorted(new.get("tags") or []):
        changes.append(_change("tags", "теги: " + (", ".join(new.get("tags") or []) or "—")))

    for part, label in (("checker", "чекер"), ("validator", "валидатор"), ("interactor", "интерактор")):
        if (old.get(part) or "") != (new.get(part) or ""):
            changes.append(_change(part, f"{label}: {old.get(part) or '—'} → {new.get(part) or '—'}"))

    old_files, new_files = old.get("files") or {}, new.get("files") or {}
    for key in sorted(set(old_files) | set(new_files)):
        o, n = old_files.get(key), new_files.get(key)
        if n is not None and o is None:
            role = ROLE_LABELS.get(file_role(new, n), "файл")
            changes.append(_change("file", f"добавлен {role} {n['name']}", name=n["name"]))
        elif o is not None and n is None:
            changes.append(_change("file", f"удалён файл {o['name']}", name=o["name"]))
        elif o is not None and n is not None and _file_changed(o, n):
            role = ROLE_LABELS.get(file_role(new, n), "файл")
            changes.append(_change("file", f"изменён {role} {n['name']}", name=n["name"]))

    old_sol, new_sol = old.get("solutions") or {}, new.get("solutions") or {}
    for name in sorted(set(old_sol) | set(new_sol)):
        o, n = old_sol.get(name), new_sol.get(name)
        if n is not None and o is None:
            changes.append(_change("solution", f"добавлено решение {name} ({n.get('tag')})", name=name))
        elif o is not None and n is None:
            changes.append(_change("solution", f"удалено решение {name}", name=name))
        elif o is not None and n is not None:
            if _file_changed(o, n):
                changes.append(_change("solution", f"изменено решение {name}", name=name))
            if o.get("tag") != n.get("tag"):
                changes.append(_change("solution", f"решение {name}: тег {o.get('tag')} → {n.get('tag')}", name=name))

    if (old.get("script") or "").strip() != (new.get("script") or "").strip():
        changes.append(_change("script", "изменён скрипт генерации тестов"))

    old_tests, new_tests = old.get("tests") or [], new.get("tests") or []
    if len(old_tests) != len(new_tests):
        changes.append(_change("tests", f"тестов: {len(old_tests)} → {len(new_tests)}"))
    else:
        def shape(tests: list[dict]) -> list[tuple]:
            return [(t.get("index"), t.get("group"), t.get("points"), t.get("useInStatements")) for t in tests]

        if shape(old_tests) != shape(new_tests):
            changes.append(_change("tests", "изменены группы/баллы/примеры тестов"))

    def groups_shape(snapshot: dict) -> dict:
        return {
            g.get("name"): (g.get("pointsPolicy"), g.get("feedbackPolicy"), tuple(sorted(g.get("dependencies") or [])))
            for g in snapshot.get("groups") or []
        }

    if groups_shape(old) != groups_shape(new):
        counts = Counter(t.get("group") for t in new_tests if t.get("group"))
        summary = ", ".join(f"{g}: {c} т." for g, c in sorted(counts.items())) or "без групп"
        changes.append(_change("groups", f"изменены группы тестов ({summary})"))

    old_pkgs = {p["id"]: p for p in old.get("packages") or []}
    newest_known = max(old_pkgs, default=0)
    for p in sorted(new.get("packages") or [], key=lambda p: p["id"]):
        prev = old_pkgs.get(p["id"])
        state = PACKAGE_STATES.get(p.get("state") or "", p.get("state"))
        if prev is None and p["id"] > newest_known:
            changes.append(_change("package", f"новый пакет #{p['id']} (rev. {p.get('revision')}): {state}",
                                   package_id=p["id"], state=p.get("state")))
        elif prev is not None and prev.get("state") != p.get("state") and p.get("state") in ("READY", "FAILED"):
            changes.append(_change("package", f"пакет #{p['id']}: {state}", package_id=p["id"], state=p.get("state")))

    return changes


def summarize(changes: list[dict], limit: int = 3) -> str:
    """A one-line title for a notification."""
    if not changes:
        return "Без изменений"
    head = "; ".join(c["text"] for c in changes[:limit])
    rest = len(changes) - limit
    return head + (f" и ещё {rest}" if rest > 0 else "")
