"""Unit tests for api.user.polygon.archive.parser.

Covers the pure text/XML/section-parsing helpers, the dataclasses, the
in-memory zip readers (with synthetic zips built on the fly), test assembly
(build_tests) and the PDF-derived parsing logic (line_to_tex, cell_to_tex,
classify_table, extract_page_items, split_statements) driven by synthetic
span/block dicts and fake ``fitz`` objects. ``fitz`` itself is only touched
through ``fitz.Rect`` (real geometry) and through monkeypatched fakes for the
page/document objects.
"""
from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

import api.user.polygon.archive.parser as P
from api.user.polygon.archive.parser import (
    Statement,
    TaskData,
    apply_meta,
    build_tests,
    classify_table,
    detect_decoration_images,
    detect_running_header,
    discover_tasks,
    line_to_tex,
    normalize_text,
    open_inner_zip,
    parse_dependencies,
    parse_desc_tag,
    parse_memory_limit,
    parse_time_limit,
    polygon_prefix_from_archive,
    polygon_test_norm,
    read_raw_tests,
    read_solutions,
    render_scoring_table,
    render_section,
    split_statements,
    tex_escape,
    math_escape,
)


# ---------------------------------------------------------------------------
# helpers to build synthetic zips
# ---------------------------------------------------------------------------


def _zip(files: dict[str, bytes]) -> zipfile.ZipFile:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    buf.seek(0)
    return zipfile.ZipFile(buf)


def _span(text, size=10.0, oy=100.0, flags=0, x0=0.0, x1=None):
    if x1 is None:
        x1 = x0 + len(text) * 5.0
    return {
        "text": text,
        "size": size,
        "flags": flags,
        "origin": (x0, oy),
        "bbox": (x0, oy - 8, x1, oy + 2),
    }


def _line(spans):
    return {"spans": spans, "bbox": (0, 90, 500, 110)}


# ---------------------------------------------------------------------------
# dataclasses
# ---------------------------------------------------------------------------


def test_statement_scoring_rows_returns_first_table_body():
    rows = [["№", "тесты", "баллы"], ["1", "1-2", "30"], ["2", "3", "70"]]
    st = Statement(letter="A", scoring=["some intro", ("table", "scoring", rows)])
    assert st.scoring_rows() == [["1", "1-2", "30"], ["2", "3", "70"]]


def test_statement_scoring_rows_empty_when_no_table():
    st = Statement(letter="A", scoring=["only text"])
    assert st.scoring_rows() == []


def test_taskdata_defaults():
    td = TaskData(name="A")
    assert td.solutions == [] and td.tests == [] and td.groups == []
    assert td.statement is None and td.dropped_tests == []


# ---------------------------------------------------------------------------
# small pure helpers
# ---------------------------------------------------------------------------


def test_parse_desc_tag_maps_known_tags():
    assert parse_desc_tag("Tag: MAIN\n") == "MA"
    assert parse_desc_tag("Tag: ACCEPTED") == "OK"
    assert parse_desc_tag("Tag: WRONG_ANSWER") == "WA"


def test_parse_desc_tag_unknown_and_missing():
    assert parse_desc_tag("Tag: SOMETHING_ELSE") is None
    assert parse_desc_tag("no tag here") is None


def test_normalize_text_strips_and_drops_trailing_blanks():
    assert normalize_text(b"  a \n b  \n\n\n") == "a\nb"
    assert normalize_text("x\r\n") == "x"


def test_parse_dependencies_ranges_and_singletons():
    assert parse_dependencies("1 - 3") == ["1", "2", "3"]
    assert parse_dependencies("2") == ["2"]
    assert parse_dependencies("1, 4") == ["1", "4"]
    assert parse_dependencies("") == []
    # mixed with en-dash and semicolon
    assert parse_dependencies("1–2; 5") == ["1", "2", "5"]


def test_polygon_test_norm():
    assert polygon_test_norm(b"a\r\nb  \r\n\r\n") == b"a\nb\n"
    assert polygon_test_norm(b"x") == b"x\n"


def test_parse_time_limit():
    assert parse_time_limit("2 секунды") == 2000
    assert parse_time_limit("1,5 с") == 1500
    assert parse_time_limit("0.25") == 250
    assert parse_time_limit("no number") is None


def test_parse_memory_limit():
    assert parse_memory_limit("256 мегабайт") == 256
    assert parse_memory_limit("МБ") is None


def test_polygon_prefix_from_archive():
    assert polygon_prefix_from_archive("2022-01-11-BelOI2022-stage3-day1") == "beloi22-1"
    assert polygon_prefix_from_archive("2020-12-01-Training-day-2") == "beloi20-2"
    assert polygon_prefix_from_archive("BelOI2022-stage3") is None  # no 'day'
    assert polygon_prefix_from_archive("day3-only") is None  # no 4-digit year


# ---------------------------------------------------------------------------
# apply_meta
# ---------------------------------------------------------------------------


def test_apply_meta_sets_limits_and_files():
    st = Statement(letter="A")
    apply_meta(st, "Ограничение по времени", "2 секунды")
    apply_meta(st, "Ограничение по памяти", "256 МБ")
    apply_meta(st, "Имя входного файла", "стандартный ввод")
    apply_meta(st, "Имя выходного файла", "output.txt")
    assert st.time_limit_ms == 2000
    assert st.memory_limit_mb == 256
    assert st.input_file == "stdin"
    assert st.output_file == "output.txt"


# ---------------------------------------------------------------------------
# zip readers
# ---------------------------------------------------------------------------


def test_open_inner_zip_found_and_missing():
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("hello.txt", b"hi")
    inner.seek(0)
    outer = _zip({"Solutions.zip": inner.getvalue(), "other.txt": b"x"})
    z = open_inner_zip(outer, "Solutions.zip")
    assert z.read("hello.txt") == b"hi"
    with pytest.raises(FileNotFoundError):
        open_inner_zip(outer, "Tests.zip")


def test_discover_tasks():
    z = _zip(
        {
            "Tests/A/tests/01": b"1",
            "Tests/B/tests/01": b"1",
            "Tests/A/tests/02": b"1",
            "Tests/": b"",  # dir-ish entry with empty second part ignored
            "other/x": b"1",
        }
    )
    assert discover_tasks(z) == ["A", "B"]


def test_read_solutions_with_and_without_desc():
    z = _zip(
        {
            "Solutions/A/solutions/main.cpp": b"int main(){}",
            "Solutions/A/solutions/main.cpp.desc": b"Tag: MAIN\n",
            "Solutions/A/solutions/wa.cpp": b"bad",  # no .desc -> tag None
            "Solutions/B/solutions/other.cpp": b"nope",  # different task
        }
    )
    sols = read_solutions(z, "A")
    by_name = {s.name: s for s in sols}
    assert set(by_name) == {"main.cpp", "wa.cpp"}
    assert by_name["main.cpp"].tag == "MA"
    assert by_name["main.cpp"].data == b"int main(){}"
    assert by_name["wa.cpp"].tag is None


def test_read_raw_tests_both_layouts_and_skips_answers():
    z = _zip(
        {
            "Tests/A/tests/samples/01": b"in1",
            "Tests/A/tests/samples/01.a": b"ans",  # .a skipped
            "Tests/A/tests/grp1/01": b"in2",
            "Tests/A/group2/01": b"in3",  # layout without 'tests'
        }
    )
    raw = read_raw_tests(z, "A")
    folders = {(folder, fname): data for folder, fname, data in raw}
    assert folders[("samples", "01")] == b"in1"
    assert folders[("grp1", "01")] == b"in2"
    assert folders[("group2", "01")] == b"in3"
    # no .a entries
    assert all(not fn.endswith(".a") for _, fn, _ in raw)


# ---------------------------------------------------------------------------
# build_tests
# ---------------------------------------------------------------------------


def test_build_tests_samples_first_continuous_numbering():
    raw = [
        ("grp1", "01", b"100\n"),
        ("samples", "01", b"sample\n"),
    ]
    tests, groups, dropped = build_tests(raw, None)
    assert [t.name for t in tests] == ["01", "02"]
    assert tests[0].is_sample is True
    assert tests[0].folder == "samples"
    assert tests[1].is_sample is False
    assert groups == [] and dropped == []


def test_build_tests_deduplicates_keeping_first():
    raw = [
        ("samples", "01", b"dup\n"),
        ("grp1", "01", b"dup\n"),  # same after norm -> dropped
        ("grp1", "02", b"unique\n"),
    ]
    tests, _, dropped = build_tests(raw, None)
    assert dropped == ["grp1/01"]
    assert len(tests) == 2


def test_build_tests_detects_sample_folder_by_examples():
    st = Statement(letter="A", examples=[("hello\n", "world\n")])
    raw = [
        ("", "01", b"hello\n"),  # empty folder, matches example -> sample
        ("grp1", "01", b"data\n"),
    ]
    tests, _, _ = build_tests(raw, st)
    sample = next(t for t in tests if t.folder == "")
    assert sample.is_sample is True


def test_build_tests_groups_from_scoring_with_points_on_last():
    rows = [
        ["№", "Тесты", "Баллы", "Зависимости"],
        ["1", "1", "30", ""],
        ["2", "2-3", "70", "1"],
    ]
    st = Statement(letter="A", scoring=[("table", "scoring", rows)])
    raw = [
        ("samples", "01", b"s\n"),
        ("grp1", "01", b"a\n"),
        ("grp2", "01", b"b\n"),
        ("grp2", "02", b"c\n"),
    ]
    tests, groups, _ = build_tests(raw, st)
    # group "0" for samples, "1" and "2" for the two regular folders
    names = [g.name for g in groups]
    assert names == ["0", "1", "2"]
    g2 = next(g for g in groups if g.name == "2")
    assert g2.points == 70
    assert g2.dependencies == ["1"]
    # points go on the LAST test of the group; earlier tests get 0
    grp2_tests = sorted((t for t in tests if t.group == "2"), key=lambda t: t.index)
    assert grp2_tests[0].points == 0
    assert grp2_tests[-1].points == 70


def test_build_tests_no_groups_when_counts_mismatch():
    rows = [["№", "Тесты", "Баллы"], ["1", "1", "100"]]
    st = Statement(letter="A", scoring=[("table", "scoring", rows)])
    raw = [("grp1", "01", b"a\n"), ("grp2", "01", b"b\n")]  # 2 folders vs 1 row
    tests, groups, _ = build_tests(raw, st)
    assert groups == []
    assert all(t.group is None for t in tests)


# ---------------------------------------------------------------------------
# tex escaping
# ---------------------------------------------------------------------------


def test_tex_escape_specials_and_math_chars():
    assert tex_escape("a_b") == r"a\_b"
    assert tex_escape("50%") == r"50\%"
    assert tex_escape("a ≤ b") == r"a $\le$ b"


def test_math_escape_wraps_without_dollars():
    assert math_escape("a≤b") == r"a\le b"
    assert math_escape("x_y") == r"x\_y"


# ---------------------------------------------------------------------------
# line_to_tex
# ---------------------------------------------------------------------------


def test_line_to_tex_plain_text():
    line = _line([_span("Hello world")])
    assert line_to_tex(line) == "Hello world"


def test_line_to_tex_empty_when_no_text():
    line = _line([_span("   ")])
    assert line_to_tex(line) == ""


def test_line_to_tex_superscript():
    # main span on baseline, small high span = superscript (10^5)
    base = _span("10", size=10.0, oy=100.0, x0=0.0, x1=10.0)
    sup = _span("5", size=6.0, oy=95.0, x0=10.0, x1=14.0)
    out = line_to_tex(_line([base, sup]))
    assert out == "10$^{5}$"


def test_line_to_tex_subscript():
    base = _span("a", size=10.0, oy=100.0, x0=0.0, x1=6.0)
    sub = _span("i", size=6.0, oy=105.0, x0=6.0, x1=9.0)
    out = line_to_tex(_line([base, sub]))
    assert out == "a$_{i}$"


def test_line_to_tex_italic_math_variable():
    # flag 2 == italic; a bare math token gets wrapped in $...$
    italic = _span("n", size=10.0, oy=100.0, flags=2, x0=0.0, x1=6.0)
    out = line_to_tex(_line([italic]))
    assert out == "$n$"


def test_line_to_tex_inserts_space_on_gap():
    a = _span("foo", size=10.0, oy=100.0, x0=0.0, x1=10.0)
    # big horizontal gap -> a space is inserted
    b = _span("bar", size=10.0, oy=100.0, x0=50.0, x1=60.0)
    out = line_to_tex(_line([a, b]))
    assert out == "foo bar"


# ---------------------------------------------------------------------------
# classify_table
# ---------------------------------------------------------------------------


class _FakeTable:
    def __init__(self, rows, bbox=(0, 0, 100, 100)):
        self._rows = rows
        self.bbox = bbox

    def extract(self):
        return self._rows


def test_classify_table_scoring():
    t = _FakeTable([["№", "Тесты", "Баллы"], ["1", "1", "100"]])
    assert classify_table(t) == "scoring"


def test_classify_table_examples_stdin():
    t = _FakeTable([["стандартный ввод", "стандартный вывод"], ["1", "2"]])
    assert classify_table(t) == "examples"


def test_classify_table_examples_input_output():
    t = _FakeTable([["input.txt", "output.txt"]])
    assert classify_table(t) == "examples"


def test_classify_table_unknown():
    t = _FakeTable([["foo", "bar", "baz"]])
    assert classify_table(t) is None


# ---------------------------------------------------------------------------
# detect_running_header / detect_decoration_images
# ---------------------------------------------------------------------------


def test_detect_running_header():
    pages = [
        [("line", "Header"), ("line", "body a")],
        [("line", "Header"), ("line", "body b")],
        [("line", "Header"), ("line", "body c")],
    ]
    assert detect_running_header(pages) == {"Header"}


def test_detect_decoration_images():
    logo = b"LOGO-BYTES"
    other = b"UNIQUE"
    d_logo = hashlib.md5(logo).hexdigest()
    pages = [
        [("image", "png", logo)],
        [("image", "png", logo)],
        [("image", "png", other)],
    ]
    assert detect_decoration_images(pages) == {d_logo}


# ---------------------------------------------------------------------------
# render_section / render_scoring_table
# ---------------------------------------------------------------------------


def test_render_scoring_table():
    out = render_scoring_table([["a", "b"], ["1", "2"]])
    assert r"\begin{tabular}{|c|c|}" in out
    assert r"a & b \\ \hline" in out
    assert out.startswith(r"\begin{center}")
    assert out.strip().endswith(r"\end{center}")


def test_render_scoring_table_empty():
    assert render_scoring_table([]) == ""


def test_render_section_joins_paragraph_and_dehyphenates():
    items = ["This is a sen-", "tence."]
    # trailing hyphen joins to next chunk
    assert render_section(items) == "This is a sentence."


def test_render_section_with_image_and_table():
    items = [
        "intro",
        ("image", "pic1.png"),
        ("table", "scoring", [["a"]]),
    ]
    out = render_section(items)
    assert "intro" in out
    assert r"\includegraphics{pic1.png}" in out
    assert r"\begin{tabular}" in out
    # chunks joined by blank lines
    assert "\n\n" in out


# ---------------------------------------------------------------------------
# cell_to_tex (uses a fake page)
# ---------------------------------------------------------------------------


class _FakePageForCell:
    def __init__(self, blocks):
        self._blocks = blocks

    def get_text(self, mode, clip=None):
        return {"blocks": self._blocks}


def test_cell_to_tex_joins_lines(monkeypatch):
    page = _FakePageForCell(
        [
            {"type": 0, "lines": [_line([_span("Hello")]), _line([_span("World")])]},
            {"type": 1, "lines": []},  # non-text block ignored
        ]
    )
    out = P.cell_to_tex(page, (0, 0, 100, 100))
    assert out == "Hello World"


def test_cell_to_tex_skips_blank_lines():
    page = _FakePageForCell(
        [{"type": 0, "lines": [_line([_span("X")]), _line([_span("  ")])]}]
    )
    out = P.cell_to_tex(page, (0, 0, 100, 100))
    assert out == "X"


# ---------------------------------------------------------------------------
# extract_page_items (fake page with tables + text blocks)
# ---------------------------------------------------------------------------


class _FakeFinder:
    def __init__(self, tables):
        self.tables = tables


class _FakeRowTable:
    """Mimics a fitz table with .extract() and .rows[].cells / .bbox."""

    def __init__(self, header_rows, bbox, cell_rows=None):
        self._extract = header_rows
        self.bbox = bbox
        self._cell_rows = cell_rows or []

    def extract(self):
        return self._extract

    @property
    def rows(self):
        class _R:
            def __init__(self, cells):
                self.cells = cells

        return [_R(cells) for cells in self._cell_rows]


class _FakePage:
    def __init__(self, tables, text_dict):
        self._finder = _FakeFinder(tables)
        self._text_dict = text_dict

    def find_tables(self):
        return self._finder

    def get_text(self, mode, clip=None):
        # cell_to_tex calls with clip; return an empty body for simplicity
        if clip is not None:
            return {"blocks": []}
        return self._text_dict


def test_extract_page_items_examples_table_and_text_lines():
    examples_tbl = _FakeRowTable(
        header_rows=[["стандартный ввод", "стандартный вывод"], ["3", "9"]],
        bbox=(0, 200, 200, 250),
    )
    text_dict = {
        "blocks": [
            {
                "type": 0,
                "bbox": (0, 50, 300, 70),
                "lines": [_line([_span("Some legend text")])],
            }
        ]
    }
    page = _FakePage([examples_tbl], text_dict)
    items = P.extract_page_items(page)
    kinds = [it[0] for it in items]
    assert "line" in kinds
    assert ("table", "examples", [["3", "9"]]) in items
    # the text line appears before the table (lower y0)
    assert items[0] == ("line", "Some legend text")


def test_extract_page_items_skips_small_and_keeps_large_image():
    text_dict = {
        "blocks": [
            {"type": 1, "width": 10, "height": 10, "image": b"icon", "ext": "png", "bbox": (0, 10, 10, 20)},
            {"type": 1, "width": 100, "height": 100, "image": b"big", "ext": "jpg", "bbox": (0, 30, 130, 130)},
        ]
    }
    page = _FakePage([], text_dict)
    items = P.extract_page_items(page)
    images = [it for it in items if it[0] == "image"]
    assert images == [("image", "jpg", b"big")]


# ---------------------------------------------------------------------------
# split_statements (fake document built from extract_page_items output)
# ---------------------------------------------------------------------------


def test_split_statements_parses_meta_sections_examples_and_images(monkeypatch):
    logo = b"LOGOLOGO"
    pic = b"PICTURE-DATA"

    # Each "page" is just a precomputed list of items; we monkeypatch
    # extract_page_items so split_statements consumes our synthetic stream.
    page_items = [
        [
            ("image", "png", logo),
            ("line", "Задача A. Сложение"),
            ("line", "Ограничение по времени: 2 секунды"),
            ("line", "Ограничение по памяти: 256 мегабайт"),
            ("line", "Имя входного файла: стандартный ввод"),
            ("line", "Имя выходного файла: стандартный вывод"),
            ("line", "Даны два числа."),
            ("image", "png", pic),
            ("line", "Формат входных данных"),
            ("line", "Два целых числа."),
            ("line", "Примеры"),
            ("table", "examples", [["1 2", "3"]]),
            ("line", "Замечание"),
            ("line", "Будьте внимательны."),
        ],
        # second page repeats logo (decoration) + a footer
        [
            ("image", "png", logo),
            ("line", "Страница 2 из 2"),
        ],
    ]
    it = iter(page_items)
    monkeypatch.setattr(P, "extract_page_items", lambda page: next(it))

    # fake fitz.Document: iterating yields one entry per page
    fake_doc = [object(), object()]
    statements = split_statements(fake_doc)

    assert len(statements) == 1
    st = statements[0]
    assert st.letter == "A"
    assert st.title == "Сложение"
    assert st.time_limit_ms == 2000
    assert st.memory_limit_mb == 256
    assert st.input_file == "stdin"
    assert st.output_file == "stdout"
    # legend got the body line + the (non-decoration) picture
    assert "Даны два числа." in st.legend
    assert ("image", "pic1.png") in st.legend
    assert st.images and st.images[0][0] == "pic1.png" and st.images[0][1] == pic
    # input_format section captured
    assert "Два целых числа." in st.input_format
    # examples table -> tuples
    assert st.examples == [("1 2", "3")]
    # notes section
    assert "Будьте внимательны." in st.notes


def test_split_statements_meta_split_across_lines(monkeypatch):
    page_items = [
        [
            ("line", "Задача B. Тест"),
            ("line", "Ограничение по времени:"),  # value on next line
            ("line", "3 секунды"),
            ("line", "Текст."),
        ]
    ]
    it = iter(page_items)
    monkeypatch.setattr(P, "extract_page_items", lambda page: next(it))
    st = split_statements([object()])[0]
    assert st.time_limit_ms == 3000
    assert "Текст." in st.legend


def test_split_statements_scoring_table_attaches_to_scoring(monkeypatch):
    rows = [["№", "Тесты", "Баллы"], ["1", "1", "100"]]
    page_items = [
        [
            ("line", "Задача C. С"),
            ("line", "Система оценки"),
            ("table", "scoring", rows),
        ]
    ]
    it = iter(page_items)
    monkeypatch.setattr(P, "extract_page_items", lambda page: next(it))
    st = split_statements([object()])[0]
    assert ("table", "scoring", rows) in st.scoring
    assert st.scoring_rows() == [["1", "1", "100"]]
