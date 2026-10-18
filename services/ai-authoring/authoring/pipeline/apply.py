"""Applying parsed model edits to the problem on Polygon.

Edits outside the allowed targets are dropped (and reported), so a request to
fix the generator never rewrites the statement. Statement edits are merged
into the current statement because the backend saves all sections at once.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

from authoring.llm.protocol import (
    Edit,
    FileEdit,
    GroupsEdit,
    LimitsEdit,
    SampleEdit,
    ScriptEdit,
    StandardChecker,
    StatementEdit,
    TagsEdit,
)
from authoring.pipeline.context import RunContext
from authoring.polygon.client import PolygonError
from authoring.sync.dossier import MAX_FILE_CHARS

logger = logging.getLogger(__name__)

STATEMENT_FIELDS = ("name", "legend", "input", "output", "scoring", "interaction", "notes", "tutorial")
TL_RANGE = (250, 15000)
ML_RANGE = (4, 1024)

# edits of these targets change what the package is built from
BUILD_TARGETS = frozenset({
    "solution", "validator", "checker", "interactor", "generator", "script", "limits", "samples",
})


@dataclass
class ApplyResult:
    changed: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    targets: set[str] = field(default_factory=set)
    plans: list[dict] = field(default_factory=list)

    @property
    def needs_build(self) -> bool:
        return bool(self.targets & BUILD_TARGETS)

    def merge(self, other: ApplyResult) -> None:
        self.changed += other.changed
        self.dropped += other.dropped
        self.errors += other.errors
        self.targets |= other.targets
        self.plans += other.plans

    def report(self) -> str:
        """Markdown lines for the chat."""
        lines = []
        if self.changed:
            lines.append("**Изменено:** " + ", ".join(self.changed))
        if self.dropped:
            lines.append("**Не применено (вне запроса):** " + ", ".join(self.dropped))
        if self.errors:
            lines.append("**Ошибки:**\n" + "\n".join(f"- {e}" for e in self.errors))
        return "\n\n".join(lines)


def describe(edit: Edit) -> str:
    if isinstance(edit, FileEdit):
        return f"{edit.name}" + (f" [{edit.tag}]" if edit.tag else "")
    if isinstance(edit, StatementEdit):
        return f"условие: {edit.field} ({edit.lang})"
    if isinstance(edit, ScriptEdit):
        return "скрипт тестов"
    if isinstance(edit, LimitsEdit):
        parts = []
        if edit.time_limit is not None:
            parts.append(f"TL {edit.time_limit} мс")
        if edit.memory_limit is not None:
            parts.append(f"ML {edit.memory_limit} МБ")
        return "лимиты: " + ", ".join(parts)
    if isinstance(edit, TagsEdit):
        return "теги"
    if isinstance(edit, StandardChecker):
        return f"чекер {edit.name}"
    if isinstance(edit, SampleEdit):
        return "пример"
    if isinstance(edit, GroupsEdit):
        return "план групп"
    return type(edit).__name__


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


async def apply_edits(
    ctx: RunContext,
    edits: Sequence[Edit],
    *,
    allowed: set[str] | None = None,
    commit_message: str | None = None,
) -> ApplyResult:
    """Apply ``edits`` (restricted to ``allowed`` targets when given)."""
    result = ApplyResult()
    snapshot = await ctx.snapshot()
    client, pid = ctx.client, ctx.session.polygon_id

    accepted: list[Edit] = []
    for edit in edits:
        if allowed is not None and edit.target not in allowed:
            result.dropped.append(describe(edit))
        else:
            accepted.append(edit)

    async def attempt(label: str, coro) -> bool:  # type: ignore[no-untyped-def]
        try:
            await coro
        except PolygonError as e:
            result.errors.append(f"{label}: {e.message}")
            logger.info("apply %s failed: %s", label, e.message)
            return False
        result.changed.append(label)
        return True

    # limits
    for edit in [e for e in accepted if isinstance(e, LimitsEdit)]:
        tl = _clamp(edit.time_limit // 50 * 50, *TL_RANGE) if edit.time_limit else None
        ml = _clamp(edit.memory_limit, *ML_RANGE) if edit.memory_limit else None
        if await attempt(describe(LimitsEdit(tl, ml)), client.update_info(pid, time_limit=tl, memory_limit=ml)):
            result.targets.add("limits")

    # statements, merged per language
    by_lang: dict[str, dict[str, str]] = {}
    for edit in [e for e in accepted if isinstance(e, StatementEdit)]:
        by_lang.setdefault(edit.lang, {})[edit.field] = edit.content
    statements: dict = {}
    if by_lang:
        # merge into the statement as it is NOW (the snapshot may be minutes old or
        # incomplete); without it we would blank the sections we do not send
        try:
            statements = await client.statements(pid)
        except PolygonError as e:
            result.errors.append(f"условие не изменено: не удалось прочитать текущее ({e.message})")
            by_lang = {}
    for lang, fields in by_lang.items():
        current = dict(statements.get(lang) or {})
        if not current.get("name") and "name" not in fields:
            other = next((s.get("name") for s in statements.values() if s.get("name")), None)
            fields.setdefault("name", other or f"Problem {pid}")
        merged = {f: current.get(f) for f in STATEMENT_FIELDS}
        merged.update(fields)
        if "name" in fields:
            merged["name"] = " ".join(str(fields["name"]).split())
        # None = keep the section; the backend resets legend/input/output when omitted
        body = dict(merged)
        for required in ("legend", "input", "output"):
            body[required] = body.get(required) or ""
        label = f"условие ({lang}): " + ", ".join(sorted(fields))
        if await attempt(label, client.save_statement(pid, lang, body)):
            result.targets.add("statement")

    for edit in [e for e in accepted if isinstance(e, TagsEdit)]:
        if await attempt("теги", client.save_tags(pid, edit.tags)):
            result.targets.add("tags")

    # files: validator/checker/interactor first, then generators, then solutions
    files = [e for e in accepted if isinstance(e, FileEdit)]
    order = {"validator": 0, "checker": 1, "interactor": 2, "generator": 3, "source": 3, "solution": 4}
    solutions = snapshot.get("solutions") or {}
    known_files = {**{e["name"]: e for e in (snapshot.get("files") or {}).values()}, **solutions}
    for edit in sorted(files, key=lambda e: order.get(e.role, 9)):
        existing_file = known_files.get(edit.name) or {}
        if len(existing_file.get("content") or "") > MAX_FILE_CHARS:
            # the model saw only the beginning of this file: a "full" rewrite would cut it
            result.errors.append(f"{edit.name}: файл слишком большой для правки ИИ, изменение не применено")
            continue
        if edit.role == "validator":
            ok = await attempt(f"валидатор {edit.name}", client.set_validator(pid, edit.name, edit.content))
        elif edit.role == "checker":
            ok = await attempt(f"чекер {edit.name}", client.set_checker(pid, edit.name, edit.content))
        elif edit.role == "interactor":
            ok = await attempt(f"интерактор {edit.name}", client.set_interactor(pid, edit.name, edit.content))
        elif edit.role in ("generator", "source"):
            ok = await attempt(edit.name, client.save_file(pid, "source", edit.name, edit.content))
        else:  # solution
            existing = solutions.get(edit.name) or {}
            tag = edit.tag or existing.get("tag") or "OK"
            if tag == "MA":
                for other_name, other in solutions.items():
                    if other_name != edit.name and other.get("tag") == "MA" and other.get("content") is not None:
                        await attempt(
                            f"{other_name} [OK]", client.save_solution(pid, other_name, other["content"], "OK")
                        )
            ok = await attempt(f"{edit.name} [{tag}]", client.save_solution(pid, edit.name, edit.content, tag))
        if ok:
            result.targets.add(edit.target)

    for edit in [e for e in accepted if isinstance(e, StandardChecker)]:
        if await attempt(f"чекер {edit.name}", client.set_checker(pid, edit.name, None)):
            result.targets.add("checker")

    for edit in [e for e in accepted if isinstance(e, ScriptEdit)]:
        if await attempt("скрипт тестов", client.save_script(pid, edit.content)):
            result.targets.add("script")

    samples = [e for e in accepted if isinstance(e, SampleEdit)]
    if samples:
        existing = [t["index"] for t in snapshot.get("tests") or [] if t.get("manual") and t.get("useInStatements")]
        for index, edit in zip(sorted(existing), samples, strict=False):
            if await attempt(f"пример {index}", client.save_test(pid, index, test_input=edit.input,
                                                                     test_use_in_statements=True)):
                result.targets.add("samples")
        if len(samples) > len(existing):
            result.errors.append(
                f"новых примеров {len(samples)}, а мест под примеры {len(existing)}: лишние не добавлены"
            )

    for edit in [e for e in accepted if isinstance(e, GroupsEdit)]:
        result.plans.append(edit.plan)

    if result.changed:
        ctx.invalidate()
        if commit_message:
            try:
                await client.commit(pid, commit_message[:200])
            except PolygonError as e:
                result.errors.append(f"commit: {e.message}")
    return result
