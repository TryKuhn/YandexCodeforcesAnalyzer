"""Olympiad archive parser (port of ParseArchive).

The archive is a zip containing nested Solutions.zip / Tests.zip /
Statements.zip and is parsed into per-problem ``TaskData``:

- solutions, with Polygon verdict tags taken from sibling ``.desc`` files;
- tests grouped into testsets (samples first, then renumbered sequentially);
- statements extracted from one shared PDF: text is reconstructed span-by-span
  into TeX, and the "Система оценки" (scoring) and "Примеры" (examples) tables
  are recovered by their on-page coordinates.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import fitz

SOURCE_EXTENSIONS = {
    ".c", ".cpp", ".cc", ".cxx", ".c++",
    ".pas", ".dpr",
    ".java", ".kt", ".py", ".cs", ".go", ".rs", ".rb", ".scala", ".d", ".php",
}
"""Source-file extensions Polygon accepts as solutions."""

DESC_TAG_TO_POLYGON = {
    "MAIN": "MA",
    "ACCEPTED": "OK",
    "OK": "OK",
    "REJECTED": "RJ",
    "INCORRECT": "RJ",
    "WRONG_ANSWER": "WA",
    "TIME_LIMIT_EXCEEDED": "TL",
    "MEMORY_LIMIT_EXCEEDED": "ML",
    "PRESENTATION_ERROR": "PE",
    "TIME_LIMIT_EXCEEDED_OR_ACCEPTED": "TO",
}
"""Map archive ``.desc`` verdict tags to Polygon solution tags."""


@dataclass
class Solution:
    """A solution file; ``tag`` is its Polygon tag (MA/OK/RJ/...) or ``None``."""

    name: str
    data: bytes
    tag: str | None


@dataclass
class Test:
    """A single test; ``index`` is its 1..N sequential number across the testset."""

    index: int
    name: str
    data: bytes
    folder: str
    group: str | None = None
    points: int | None = None
    is_sample: bool = False


@dataclass
class TestGroup:
    """A scoring group with its point value and dependency group names."""

    name: str
    points: int | None
    dependencies: list[str] = field(default_factory=list)


@dataclass
class Statement:
    """A parsed problem statement.

    Section fields (``legend``, ``input_format``, ``output_format``,
    ``scoring``, ``notes``) are ordered lists whose items are either a TeX
    string or a ``("table", kind, rows)`` / ``("image", name)`` tuple.
    ``examples`` is a list of ``(input, output)`` pairs and ``images`` a list
    of ``(name, bytes)`` statement resources.
    """

    letter: str
    title: str = ""
    time_limit_ms: int | None = None
    memory_limit_mb: int | None = None
    input_file: str = "stdin"
    output_file: str = "stdout"
    legend: list = field(default_factory=list)
    input_format: list = field(default_factory=list)
    output_format: list = field(default_factory=list)
    scoring: list = field(default_factory=list)
    examples: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    images: list = field(default_factory=list)

    def scoring_rows(self) -> list[list[str]]:
        """Data rows of the first scoring table (header row stripped)."""
        for it in self.scoring:
            if not isinstance(it, str):
                return it[2][1:]
        return []


@dataclass
class TaskData:
    """Everything parsed for one problem; ``name`` is the archive letter (A, B, ...).

    ``dropped_tests`` lists tests skipped as duplicates during ``build_tests``.
    """

    name: str
    solutions: list[Solution] = field(default_factory=list)
    tests: list[Test] = field(default_factory=list)
    groups: list[TestGroup] = field(default_factory=list)
    statement: Statement | None = None
    dropped_tests: list[str] = field(default_factory=list)


def open_inner_zip(outer: zipfile.ZipFile, suffix: str) -> zipfile.ZipFile:
    """Open the first nested zip whose name ends with ``suffix`` (in memory)."""
    for name in outer.namelist():
        if name.endswith(suffix):
            return zipfile.ZipFile(io.BytesIO(outer.read(name)))
    raise FileNotFoundError(f"В архиве не найден {suffix}")


def discover_tasks(tests_zip: zipfile.ZipFile) -> list[str]:
    """Return sorted problem names found as ``Tests/<name>/`` subfolders."""
    tasks = set()
    for name in tests_zip.namelist():
        parts = name.split("/")
        if len(parts) >= 2 and parts[0] == "Tests" and parts[1]:
            tasks.add(parts[1])
    return sorted(tasks)


def parse_desc_tag(desc_text: str) -> str | None:
    """Read the ``Tag:`` line from a ``.desc`` file and map it to a Polygon tag."""
    m = re.search(r"^Tag:\s*(\S+)", desc_text, re.M)
    return DESC_TAG_TO_POLYGON.get(m.group(1)) if m else None


def read_solutions(solutions_zip: zipfile.ZipFile, task: str) -> list[Solution]:
    """Read a task's solutions from ``Solutions/<task>/solutions/``.

    ``.desc`` files are not solutions themselves; each solution's tag is taken
    from its sibling ``<name>.desc`` when present.
    """
    prefix = f"Solutions/{task}/solutions/"
    result = []
    for info in solutions_zip.infolist():
        if info.is_dir() or not info.filename.startswith(prefix):
            continue
        if info.filename.endswith(".desc"):
            continue
        tag = None
        try:
            desc = solutions_zip.read(info.filename + ".desc").decode("utf-8", "replace")
            tag = parse_desc_tag(desc)
        except KeyError:
            pass
        result.append(Solution(Path(info.filename).name, solutions_zip.read(info), tag))
    return result


def read_raw_tests(tests_zip: zipfile.ZipFile, task: str) -> list[tuple[str, str, bytes]]:
    """Read a task's tests as ``(group_folder, filename, data)`` tuples.

    Both archive layouts are supported: ``Tests/X/tests/<group>/NN`` (the
    leading ``tests`` folder is stripped) and ``Tests/X/<group>/NN``. Jury
    answer files (``.a``) are skipped.
    """
    prefix = f"Tests/{task}/"
    result = []
    for info in tests_zip.infolist():
        if info.is_dir() or not info.filename.startswith(prefix):
            continue
        if info.filename.endswith(".a"):
            continue
        rel = info.filename[len(prefix):]
        parts = rel.split("/")
        folder = "/".join(parts[:-1])
        if folder == "tests":
            folder = ""
        elif folder.startswith("tests/"):
            folder = folder[len("tests/"):]
        result.append((folder, parts[-1], tests_zip.read(info)))
    return result


def normalize_text(data: bytes | str) -> str:
    """Decode and trim text: strip per-line whitespace and trailing blank lines.

    Used to compare test contents against statement examples.
    """
    text = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
    lines = [ln.strip() for ln in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def parse_dependencies(cell: str) -> list[str]:
    """Parse a dependency cell into group names.

    Expands ranges and lists: '1 - 3' -> ['1','2','3']; '2' -> ['2'];
    '1, 4' -> ['1','4']; '' -> [].
    """
    deps: list[int] = []
    for part in re.split(r"[,;]", cell):
        m = re.match(r"\s*(\d+)\s*[-–—]\s*(\d+)\s*$", part)
        if m:
            deps.extend(range(int(m.group(1)), int(m.group(2)) + 1))
        else:
            m = re.match(r"\s*(\d+)\s*$", part)
            if m:
                deps.append(int(m.group(1)))
    return [str(d) for d in deps]


def polygon_test_norm(data: bytes) -> bytes:
    r"""Normalize a test the way Polygon does for its "well-formed" comparison.

    Converts ``\r\n`` / ``\r`` to ``\n``, right-trims each line, drops trailing
    blank lines and ensures a single trailing newline. Polygon compares tests
    after this normalization, so duplicates are detected on the result.
    """
    text = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    lines = [ln.rstrip() for ln in text.split(b"\n")]
    while lines and not lines[-1]:
        lines.pop()
    return b"\n".join(lines) + b"\n"


def build_tests(
    raw: list[tuple[str, str, bytes]], statement: Statement | None
) -> tuple[list[Test], list[TestGroup], list[str]]:
    """Renumber tests and detect samples and scoring groups.

    Returns ``(tests, groups, dropped)``. A folder is treated as samples when
    it is named ``samples``, or when it is the default folder and every test in
    it matches a statement example. Scoring groups are only enabled when the
    number of non-sample folders equals the number of scoring-table rows, so
    folders map one-to-one onto groups. Duplicate tests (which Polygon forbids
    in one testset) are dropped, keeping the first occurrence with samples
    prioritized; their paths are returned as ``dropped`` for the log. All group
    points are placed on the group's last test.
    """
    by_folder: dict[str, list[tuple[str, bytes]]] = {}
    for folder, fname, data in raw:
        by_folder.setdefault(folder, []).append((fname, data))
    for files in by_folder.values():
        files.sort(key=lambda x: x[0])

    examples = {normalize_text(inp) for inp, _ in (statement.examples if statement else [])}

    def is_sample_folder(folder: str) -> bool:
        if folder == "samples":
            return True
        if folder in ("", "tests") and examples:
            return all(normalize_text(d) in examples for _, d in by_folder[folder])
        return False

    sample_folders = sorted(f for f in by_folder if is_sample_folder(f))
    regular_folders = sorted(
        (f for f in by_folder if f not in sample_folders),
        key=lambda f: (int(m.group()) if (m := re.search(r"\d+", f)) else 10**9, f),
    )

    seen_hashes: set[str] = set()
    dropped: list[str] = []
    for folder in sample_folders + regular_folders:
        kept = []
        for fname, data in by_folder[folder]:
            h = hashlib.md5(polygon_test_norm(data)).hexdigest()
            if h in seen_hashes:
                dropped.append(f"{folder}/{fname}" if folder else fname)
                continue
            seen_hashes.add(h)
            kept.append((fname, data))
        by_folder[folder] = kept

    scoring_rows = statement.scoring_rows() if statement else []
    use_groups = bool(scoring_rows) and len(scoring_rows) == len(regular_folders)

    groups: list[TestGroup] = []
    folder_group: dict[str, TestGroup] = {}
    if use_groups:
        if sample_folders:
            g0 = TestGroup("0", points=0)
            groups.append(g0)
            for f in sample_folders:
                folder_group[f] = g0
        for i, (folder, row) in enumerate(zip(regular_folders, scoring_rows), 1):
            points_m = re.search(r"\d+", row[2]) if len(row) > 2 else None
            deps = parse_dependencies(row[3]) if len(row) > 3 else []
            g = TestGroup(str(i), points=int(points_m.group()) if points_m else None, dependencies=deps)
            groups.append(g)
            folder_group[folder] = g

    tests: list[Test] = []
    index = 0
    total = sum(len(v) for v in by_folder.values())
    width = max(2, len(str(total)))
    for folder in sample_folders + regular_folders:
        group = folder_group.get(folder)
        for pos, (fname, data) in enumerate(by_folder[folder]):
            index += 1
            tests.append(
                Test(
                    index=index,
                    name=str(index).zfill(width),
                    data=data,
                    folder=folder,
                    group=group.name if group else None,
                    points=(
                        group.points
                        if group and group.points is not None and pos == len(by_folder[folder]) - 1
                        else (0 if group and group.points is not None else None)
                    ),
                    is_sample=folder in sample_folders,
                )
            )
    return tests, groups, dropped


PROBLEM_RE = re.compile(r"^Задача\s+(\S+)\.\s*(.*)$")
PAGE_FOOTER_RE = re.compile(r"^Страница\s+\d+\s+из\s+\d+$")

SECTION_BY_HEADING = {
    "Формат входных данных": "input_format",
    "Формат выходных данных": "output_format",
    "Система оценки": "scoring",
    "Примеры": "examples",
    "Пример": "examples",
    "Замечание": "notes",
    "Замечания": "notes",
}

META_RE = re.compile(
    r"^(Имя входного файла|Имя выходного файла|"
    r"Ограничение по времени|Ограничение по памяти):\s*(.*)$"
)

MATH_CHARS = {
    "⩽": r"\leqslant",
    "⩾": r"\geqslant",
    "≤": r"\le",
    "≥": r"\ge",
    "≠": r"\ne",
    "⊕": r"\oplus",
    "×": r"\times",
    "·": r"\cdot",
    "−": "-",
    "∈": r"\in",
    "∞": r"\infty",
}

TEX_SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def tex_escape(text: str) -> str:
    """Escape text for TeX text mode (math symbols are wrapped in ``$...$``)."""
    out = []
    for ch in text:
        if ch in TEX_SPECIAL:
            out.append(TEX_SPECIAL[ch])
        elif ch in MATH_CHARS:
            out.append(f"${MATH_CHARS[ch]}$")
        else:
            out.append(ch)
    return "".join(out)


def math_escape(text: str) -> str:
    """Escape text already inside TeX math mode (no surrounding ``$``)."""
    out = []
    for ch in text:
        if ch in TEX_SPECIAL:
            out.append(TEX_SPECIAL[ch])
        elif ch in MATH_CHARS:
            out.append(MATH_CHARS[ch] + " ")
        else:
            out.append(ch)
    return "".join(out)


MATH_TOKEN_RE = re.compile(r"[A-Za-z0-9 .,+\-*/()=<>'|!]+")


def line_to_tex(line: dict) -> str:
    """Convert one PDF line (fitz dict) into a TeX string.

    The dominant font size fixes the baseline; spans that are smaller or
    shifted above/below it are reconstructed as superscripts (powers, e.g.
    ``10^5``) or subscripts (indices, e.g. ``a_i``), and italic math variables
    are wrapped in ``$...$``. Adjacent math fragments are merged into a single
    ``$...$`` group, and gaps between spans (fitz emits no inter-span spaces in
    dict mode) are recovered from bbox x-coordinates.
    """
    spans = line["spans"]
    text_spans = [s for s in spans if s["text"].strip()]
    if not text_spans:
        return ""
    main_size = max(s["size"] for s in text_spans)
    origins = Counter(
        round(s["origin"][1], 1) for s in text_spans if s["size"] >= main_size - 0.5
    )
    baseline = origins.most_common(1)[0][0] if origins else round(text_spans[0]["origin"][1], 1)

    parts: list[list] = []
    prev_x1: float | None = None
    for s in spans:
        raw = s["text"]
        if not raw.strip():
            parts.append(["space", " "])
            prev_x1 = None
            continue
        if prev_x1 is not None and s["bbox"][0] - prev_x1 > 1.0:
            parts.append(["space", " "])
        prev_x1 = s["bbox"][2]

        oy = round(s["origin"][1], 1)
        shifted = s["flags"] & 1 or s["size"] < main_size - 0.5
        if shifted and oy < baseline - 0.5:
            kind = "sup"
        elif shifted and oy > baseline + 0.5:
            kind = "sub"
        elif (
            s["flags"] & 2
            and MATH_TOKEN_RE.fullmatch(raw.strip())
            and re.search(r"[A-Za-z0-9]", raw)
        ):
            kind = "math"
        else:
            parts.append(["text", tex_escape(raw)])
            continue
        text = math_escape(raw.strip())
        if parts and kind in ("sub", "sup") and parts[-1][0] == kind:
            parts[-1][1] += text
        else:
            parts.append([kind, text])

    res = ""
    in_math = False
    pending_space = False
    for kind, text in parts:
        if kind == "space":
            pending_space = True
            continue
        is_math = kind in ("math", "sub", "sup")
        if pending_space:
            if in_math and not is_math:
                res += "$"
                in_math = False
            res += " "
            pending_space = False
        if is_math and not in_math:
            res += "$"
            in_math = True
        elif not is_math and in_math:
            res += "$"
            in_math = False
        if kind == "sub":
            res += f"_{{{text}}}"
        elif kind == "sup":
            res += f"^{{{text}}}"
        else:
            res += text
    if in_math:
        res += "$"
    return re.sub(r"\s+", " ", res).strip()


def cell_to_tex(page: fitz.Page, bbox) -> str:
    """Extract a table cell's text (with sub/superscripts) by its bbox.

    A subscript or superscript that PyMuPDF splits onto its own line is glued
    back onto the preceding text without a space.
    """
    d = page.get_text("dict", clip=fitz.Rect(bbox))
    parts = []
    for block in d["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            t = line_to_tex(line)
            if t:
                parts.append(t)
    text = ""
    for p in parts:
        if p.startswith("$_") or p.startswith("$^"):
            text += p
        else:
            text += (" " if text else "") + p
    return text


def classify_table(table) -> str | None:
    """Classify a detected table as ``"scoring"``, ``"examples"`` or ``None``.

    Scoring tables start with a ``№`` header cell; examples tables are the
    two-column input/output tables ("стандартный ввод"/"стандартный вывод" or
    ``input``/``output`` headers).
    """
    header = [(c or "").strip() for c in table.extract()[0]]
    if header and header[0] == "№":
        return "scoring"
    if len(header) == 2 and (
        header == ["стандартный ввод", "стандартный вывод"]
        or (header[0].startswith("input") and header[1].startswith("output"))
    ):
        return "examples"
    return None


def extract_page_items(page: fitz.Page) -> list:
    """Return a page's content items in reading order (sorted by y-coordinate).

    Items are ``("line", tex)``, ``("table", kind, rows)`` or
    ``("image", ext, data)``. Examples tables keep their raw cell text (header
    dropped); other tables (scoring and unknown) have each cell rendered via
    ``cell_to_tex``. Raster images at least 40x40 are kept inline. Text blocks
    and lines whose area mostly overlaps a table rect are skipped, since that
    text is already captured by the table.
    """
    finder = page.find_tables()
    table_rects = [fitz.Rect(t.bbox) for t in finder.tables]

    items: list[tuple] = []
    for t, rect in zip(finder.tables, table_rects):
        kind = classify_table(t)
        if kind == "examples":
            rows = [
                [(c or "").strip() for c in row] for row in t.extract()[1:]
            ]
            items.append((rect.y0, ("table", "examples", rows)))
        else:
            rows = [
                [cell_to_tex(page, cell) if cell else "" for cell in row.cells]
                for row in t.rows
            ]
            items.append((rect.y0, ("table", "scoring", rows)))

    d = page.get_text("dict")

    for block in d["blocks"]:
        if block["type"] != 1:
            continue
        if block.get("width", 0) < 40 or block.get("height", 0) < 40:
            continue
        data = block.get("image")
        if not data:
            continue
        ext = block.get("ext") or "png"
        items.append((block["bbox"][1], ("image", ext, data)))

    for block in d["blocks"]:
        if block["type"] != 0:
            continue
        br = fitz.Rect(block["bbox"])
        if any(br.intersects(tr) and abs((br & tr).get_area()) > 0.5 * abs(br.get_area()) for tr in table_rects):
            continue
        for line in block["lines"]:
            lr = fitz.Rect(line["bbox"])
            if any(lr.intersects(tr) and abs((lr & tr).get_area()) > 0.5 * abs(lr.get_area()) for tr in table_rects):
                continue
            text = line_to_tex(line)
            if text:
                items.append((line["bbox"][1], ("line", text)))

    items.sort(key=lambda x: x[0])
    return [it for _, it in items]


def detect_running_header(pages_items: list[list]) -> set[str]:
    """Detect repeated running-header lines to strip them from statements.

    Examines the first three text lines of each page and returns those that
    appear on at least 80% of pages (minimum two).
    """
    counter: Counter[str] = Counter()
    for items in pages_items:
        lines = [it[1] for it in items if it[0] == "line"][:3]
        for ln in set(lines):
            counter[ln] += 1
    threshold = max(2, int(len(pages_items) * 0.8))
    return {ln for ln, c in counter.items() if c >= threshold}


def parse_time_limit(value: str) -> int | None:
    """Parse a time-limit string (seconds, possibly with comma) into milliseconds."""
    m = re.search(r"[\d.,]+", value)
    return int(float(m.group(0).replace(",", ".")) * 1000) if m else None


def parse_memory_limit(value: str) -> int | None:
    """Parse a memory-limit string into an integer number of megabytes."""
    m = re.search(r"\d+", value)
    return int(m.group(0)) if m else None


def apply_meta(st: Statement, field_name: str, value: str) -> None:
    """Apply a parsed statement-header field (limits / I/O file names) to ``st``.

    "стандартный" input/output file names are normalized to ``stdin``/``stdout``.
    """
    if field_name == "Ограничение по времени":
        st.time_limit_ms = parse_time_limit(value)
    elif field_name == "Ограничение по памяти":
        st.memory_limit_mb = parse_memory_limit(value)
    elif field_name == "Имя входного файла":
        st.input_file = "stdin" if "стандартный" in value else value
    elif field_name == "Имя выходного файла":
        st.output_file = "stdout" if "стандартный" in value else value


def detect_decoration_images(pages_items: list[list]) -> set[str]:
    """Return md5s of images recurring on most pages (logos and similar chrome).

    Threshold is 80% of pages (minimum two), so such images can be excluded
    from statement resources.
    """
    counter: Counter[str] = Counter()
    for items in pages_items:
        digests = {hashlib.md5(it[2]).hexdigest() for it in items if it[0] == "image"}
        for d in digests:
            counter[d] += 1
    threshold = max(2, int(len(pages_items) * 0.8))
    return {d for d, c in counter.items() if c >= threshold}


def split_statements(doc: fitz.Document) -> list[Statement]:
    """Split a PDF into per-problem statements, in document order.

    Walks page items in reading order. A "Задача X." line starts a new
    statement; running headers, page footers and decoration images are
    dropped. Header fields (limits, I/O files) may span two lines, so a field
    label with no value defers to the next line. Known section headings switch
    the active section. Images are stored as statement resources and recorded
    in the current section; examples tables fill ``examples`` while scoring and
    unknown tables attach to their section (defaulting to scoring).
    """
    pages_items = [extract_page_items(p) for p in doc]
    header = detect_running_header(pages_items)
    decoration = detect_decoration_images(pages_items)

    statements: list[Statement] = []
    st: Statement | None = None
    section = "legend"
    pending_meta: str | None = None

    for items in pages_items:
        for it in items:
            if it[0] == "image":
                _, ext, data = it
                if st is None or hashlib.md5(data).hexdigest() in decoration:
                    continue
                img_name = f"pic{len(st.images) + 1}.{ext}"
                st.images.append((img_name, data))
                getattr(st, section).append(("image", img_name))
                continue
            if it[0] == "line":
                ln = it[1]
                if ln in header or PAGE_FOOTER_RE.match(ln):
                    continue
                m = PROBLEM_RE.match(ln)
                if m:
                    st = Statement(letter=m.group(1), title=m.group(2))
                    statements.append(st)
                    section = "legend"
                    pending_meta = None
                    continue
                if st is None:
                    continue
                if pending_meta is not None:
                    apply_meta(st, pending_meta, ln)
                    pending_meta = None
                    continue
                mm = META_RE.match(ln)
                if mm:
                    if mm.group(2).strip():
                        apply_meta(st, mm.group(1), mm.group(2).strip())
                    else:
                        pending_meta = mm.group(1)
                    continue
                if ln in SECTION_BY_HEADING:
                    section = SECTION_BY_HEADING[ln]
                    continue
                getattr(st, section).append(ln)
            else:
                _, kind, rows = it
                if st is None:
                    continue
                if kind == "examples":
                    st.examples.extend((r[0], r[1]) for r in rows if len(r) >= 2)
                else:
                    target = st.scoring if section in ("scoring", "legend") else getattr(st, section)
                    target.append(("table", "scoring", rows))
    return statements


def render_scoring_table(rows: list[list[str]]) -> str:
    """Render table rows as a centered TeX ``tabular`` with all-bordered cells."""
    if not rows:
        return ""
    ncols = max(len(r) for r in rows)
    out = [r"\begin{center}", rf"\begin{{tabular}}{{|{'|'.join('c' * ncols)}|}}", r"\hline"]
    for r in rows:
        cells = list(r) + [""] * (ncols - len(r))
        out.append(" & ".join(cells) + r" \\ \hline")
    out += [r"\end{tabular}", r"\end{center}"]
    return "\n".join(out)


def render_section(items: list) -> str:
    """Render a statement section to TeX.

    Consecutive text lines are joined into a paragraph (a trailing hyphen joins
    a hyphenated word back together); images and tables are flushed as their
    own blocks, and paragraphs/blocks are separated by blank lines.
    """
    chunks = []
    para: list[str] = []

    def flush() -> None:
        if para:
            chunks.append(" ".join(para))
            para.clear()

    for it in items:
        if isinstance(it, str):
            if para and para[-1].endswith("-"):
                para[-1] = para[-1][:-1] + it
            else:
                para.append(it)
        elif it[0] == "image":
            flush()
            chunks.append(
                "\\begin{center}\n\\includegraphics{" + it[1] + "}\n\\end{center}"
            )
        else:
            flush()
            chunks.append(render_scoring_table(it[2]))
    flush()
    return "\n\n".join(chunks)


def polygon_prefix_from_archive(archive_stem: str) -> str | None:
    """Derive a Polygon problem-name prefix from the archive file stem.

    Combines the four-digit year (taken mod 100) and the day number, e.g.
    '2022-01-11-BelOI2022-stage3-day1' -> 'beloi22-1' and
    '2020-12-01-Training-day-2' -> 'beloi20-2'. Returns ``None`` if either part
    is missing.
    """
    ym = re.search(r"(\d{4})", archive_stem)
    dm = re.search(r"day\D*(\d+)", archive_stem, re.I)
    if not (ym and dm):
        return None
    return f"beloi{int(ym.group(1)) % 100}-{dm.group(1)}"


def parse_archive(archive_bytes: bytes) -> list[TaskData]:
    """Fully parse an archive in memory into per-problem ``TaskData``.

    CPU-bound, so it should be run in an executor. Statements are matched to
    tasks by problem letter when the letters line up with the test-folder
    names, otherwise positionally ("Задача 1." -> first task).
    """
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as outer:
        solutions_zip = open_inner_zip(outer, "Solutions.zip")
        tests_zip = open_inner_zip(outer, "Tests.zip")
        statements_zip = open_inner_zip(outer, "Statements.zip")

        task_names = discover_tasks(tests_zip)
        if not task_names:
            raise RuntimeError("В Tests.zip не найдено ни одной задачи")

        pdf_name = next(
            (n for n in statements_zip.namelist() if n.lower().endswith(".pdf")), None
        )
        statements: list[Statement] = []
        if pdf_name:
            doc = fitz.open(stream=statements_zip.read(pdf_name), filetype="pdf")
            statements = split_statements(doc)

        by_letter = {s.letter: s for s in statements}
        tasks = []
        for i, name in enumerate(task_names):
            st = by_letter.get(name)
            if st is None and i < len(statements):
                st = statements[i]
            solutions = read_solutions(solutions_zip, name)
            tests, groups, dropped = build_tests(read_raw_tests(tests_zip, name), st)
            tasks.append(TaskData(
                name=name, solutions=solutions, tests=tests, groups=groups,
                statement=st, dropped_tests=dropped,
            ))
        return tasks
