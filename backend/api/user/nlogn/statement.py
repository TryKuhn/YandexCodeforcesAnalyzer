"""Statement of a Polygon package in the format of contest.nlogn.info.

NlogN shows Codeforces/Polygon-like statements: the markup of Polygon's
``problem-statement`` with every class prefixed by ``task__my-`` (its CSS and
its own "polygonify" button use exactly this), formulas rendered by MathJax 2.
Formulas are emitted as ``<script type="math/tex">`` (``; mode=display`` for
display ones): MathJax picks them up regardless of its delimiter settings, and
the NlogN courses platform converts exactly this form for its editor.

Source, in order of preference:

1. the HTML Polygon generates into the package
   (``statements/.html/<lang>/problem.html``, Russian first);
2. the LaTeX sections (``statements/<lang>/problem-properties.json``) through a
   small LaTeX -> HTML converter -- for packages built without HTML statements.

Images are inlined as ``data:`` URIs (NlogN has no place for statement files),
anything active (scripts, styles, event handlers, links to other pages'
scripts) is dropped.
"""
from __future__ import annotations

import base64
import html
import json
import mimetypes
import posixpath
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from api.user.ejudge.common import EjudgeError
from api.user.ejudge.package import PolygonPackage

CLASS_PREFIX = "task__my-"
LANGUAGES = ("russian", "english")
MAX_IMAGE_BYTES = 2 * 1024 * 1024

# Polygon's generated HTML uses the Codeforces delimiters ($$$$$$ display, $$$ inline):
# there a lone "$" is just a dollar sign. LaTeX sources use the plain TeX ones.
_POLYGON_MATH_RE = re.compile(r"\$\$\$\$\$\$(?P<d6>.+?)\$\$\$\$\$\$|\$\$\$(?P<i3>.+?)\$\$\$", re.S)
_TEX_MATH_RE = re.compile(
    r"(?<!\\)\$\$(?P<d2>.+?)(?<!\\)\$\$"
    r"|(?<![\\$])\$(?P<i1>[^$]+?)(?<!\\)\$",
    re.S,
)
_SKIP_MATH = {"pre", "code", "script", "style", "textarea"}
_ALLOWED_TAGS = {
    "div", "span", "p", "br", "b", "strong", "i", "em", "u", "s", "sub", "sup", "small", "big", "tt",
    "code", "pre", "ul", "ol", "li", "table", "thead", "tbody", "tr", "td", "th", "center", "img",
    "a", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "blockquote", "script", "font", "dl", "dt", "dd",
}
_ALLOWED_ATTRS = {"class", "src", "alt", "width", "height", "href", "colspan", "rowspan", "align", "type",
                  "style"}
_SAFE_STYLE = re.compile(r"^[\w\s:;.,%#()-]*$")


@dataclass
class Statement:
    title: str
    html: str
    text: str
    language: str
    source: str  # "html" | "latex"


# --------------------------------------------------------------------------- helpers
def _mime(name: str) -> str:
    return mimetypes.guess_type(name)[0] or ("image/svg+xml" if name.endswith(".svg") else "image/png")


def _data_uri(name: str, content: bytes) -> str:
    return f"data:{_mime(name)};base64,{base64.b64encode(content).decode('ascii')}"


def _math_script(soup: BeautifulSoup, tex: str, display: bool) -> Tag:
    tag = soup.new_tag("script", attrs={"type": "math/tex; mode=display" if display else "math/tex"})
    # a literal "</script" would end the element early
    tag.string = tex.strip().replace("</", "<\\/")
    return tag


def _convert_math(soup: BeautifulSoup, pattern: re.Pattern[str]) -> None:
    """Formulas in text nodes (``$$$x$$$`` or ``$x$``/``$$x$$``) -> ``<script type="math/tex">``."""
    for node in list(soup.find_all(string=True)):
        if isinstance(node, Comment) or not isinstance(node, NavigableString):
            continue
        if any(p.name in _SKIP_MATH for p in node.parents if isinstance(p, Tag)):
            continue
        text = str(node)
        if "$" not in text:
            continue
        pieces: list[object] = []
        last = 0
        for m in pattern.finditer(text):
            groups = m.groupdict()
            tex = groups.get("d6") or groups.get("i3") or groups.get("d2") or groups.get("i1")
            if tex is None or not tex.strip():
                continue
            pieces.append(text[last:m.start()])
            pieces.append(_math_script(soup, tex, display=bool(groups.get("d6") or groups.get("d2"))))
            last = m.end()
        if not pieces:
            continue
        pieces.append(text[last:])
        for piece in pieces:
            if isinstance(piece, str):
                if piece:
                    node.insert_before(NavigableString(piece))
            else:
                node.insert_before(piece)  # type: ignore[arg-type]
        node.extract()


def _unescape_dollars(root: Tag) -> None:
    """A ``\\$`` left in plain text is an escaped dollar sign: NlogN's MathJax would show the backslash."""
    for node in list(root.find_all(string=True)):
        if isinstance(node, Comment) or "\\$" not in node:
            continue
        if any(p.name in _SKIP_MATH for p in node.parents if isinstance(p, Tag)):
            continue
        node.replace_with(NavigableString(str(node).replace("\\$", "$")))


def _sanitize(soup: BeautifulSoup, root: Tag) -> None:
    for comment in root.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for tag in list(root.find_all(True)):
        if tag.name in ("style", "link", "meta", "iframe", "object", "embed", "form", "input", "button",
                        "noscript", "svg"):
            tag.decompose()
            continue
        if tag.name == "script" and not str(tag.get("type", "")).startswith("math/tex"):
            tag.decompose()
            continue
        if tag.name not in _ALLOWED_TAGS:
            tag.unwrap()
            continue
        for attr in list(tag.attrs):
            value = tag.attrs[attr]
            if attr not in _ALLOWED_ATTRS or attr.startswith("on"):
                del tag.attrs[attr]
            elif attr == "href" and not str(value).startswith(("http://", "https://", "#", "mailto:")):
                del tag.attrs[attr]
            elif attr == "style" and not _SAFE_STYLE.match(str(value)):
                del tag.attrs[attr]
            elif attr == "type" and tag.name != "script":
                del tag.attrs[attr]


def _inline_images(root: Tag, files: dict[str, bytes], base_dir: str, warnings: list[str]) -> None:
    for img in root.find_all("img"):
        src = str(img.get("src") or "")
        if not src or src.startswith(("data:", "http://", "https://")):
            continue
        name = posixpath.normpath(posixpath.join(base_dir, src.split("?")[0]))
        content = files.get(name)
        if content is None:
            # the same image is usually also next to the LaTeX sources
            alt = [k for k in files if posixpath.basename(k) == posixpath.basename(name)]
            content = files.get(alt[0]) if alt else None
        if content is None:
            warnings.append(f"картинка {src} не найдена в пакете")
            img.decompose()
        elif len(content) > MAX_IMAGE_BYTES:
            warnings.append(f"картинка {src} больше 2 МБ, пропущена")
            img.decompose()
        else:
            img["src"] = _data_uri(name, content)


def _prefix_classes(root: Tag) -> None:
    for tag in [root, *root.find_all(True)]:
        classes = tag.get("class")
        if classes:
            tag["class"] = " ".join(c if c.startswith(CLASS_PREFIX) else CLASS_PREFIX + c for c in classes)


def to_text(root: Tag) -> str:
    """Plain text of the statement; formulas as ``$tex$``."""
    parts: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, Comment):
            return
        if isinstance(node, NavigableString):
            parts.append(str(node))
            return
        if not isinstance(node, Tag):
            return
        if node.name == "script":
            # get_text() skips script contents
            tex = str(node.string or "").replace("<\\/", "</")
            display = "display" in str(node.get("type", ""))
            parts.append(f"$${tex}$$" if display else f"${tex}$")
            return
        block = node.name in ("p", "div", "pre", "li", "tr", "br", "table", "h1", "h2", "h3", "h4", "ul", "ol")
        if node.name == "li":
            parts.append("\n- ")
        for child in node.children:
            walk(child)
        if node.name in ("td", "th"):
            parts.append("\t")
        if block:
            parts.append("\n")

    walk(root)
    text = "".join(parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# --------------------------------------------------------------------------- from Polygon HTML
def _html_languages(files: dict[str, bytes]) -> list[str]:
    langs = sorted({k.split("/")[1] for k in files if k.startswith(".html/") and k.endswith("/problem.html")})
    return [*[lang for lang in LANGUAGES if lang in langs], *[lang for lang in langs if lang not in LANGUAGES]]


def from_polygon_html(raw: bytes, files: dict[str, bytes], base_dir: str, warnings: list[str]) -> tuple[str, str, str]:
    """(title, html, text) from Polygon's ``problem.html``."""
    soup = BeautifulSoup(raw.decode("utf-8", errors="replace"), "html.parser")
    statement = soup.find("div", class_="problem-statement")
    if statement is None:
        raise EjudgeError("в HTML-условии пакета нет блока problem-statement")
    title_div = statement.find("div", class_="title")
    title = title_div.get_text(" ", strip=True) if title_div else ""
    # Polygon prefixes the title with the problem letter ("A. Сумма")
    title = re.sub(r"^[A-Z]\d?\.\s+", "", title)

    header = statement.find("div", class_="header")
    if header is not None:
        if title_div is not None:
            title_div.decompose()
        # standard input/output are implied on NlogN; files are worth showing
        for cls in ("input-file", "output-file"):
            div = header.find("div", class_=cls)
            if div is None:
                continue
            title_part = div.find("div", class_="property-title")
            value = div.get_text(" ", strip=True)
            if title_part is not None:
                value = value.replace(title_part.get_text(" ", strip=True), "", 1).strip()
            if value.lower() in ("стандартный ввод", "стандартный вывод", "standard input", "standard output"):
                div.decompose()

    _sanitize(soup, statement)
    _inline_images(statement, files, base_dir, warnings)
    # Polygon writes $$$...$$$; a hand-made/older HTML may use plain $...$
    _convert_math(soup, _POLYGON_MATH_RE if "$$$" in statement.get_text() else _TEX_MATH_RE)
    _unescape_dollars(statement)
    _prefix_classes(statement)
    return title, str(statement), to_text(statement)


# --------------------------------------------------------------------------- from LaTeX sources
_LATEX_SECTIONS = (
    ("legend", None, "legend"),
    ("input", ("Входные данные", "Input"), "input-specification"),
    ("output", ("Выходные данные", "Output"), "output-specification"),
    ("interaction", ("Протокол взаимодействия", "Interaction"), "interaction-specification"),
    ("scoring", ("Система оценки", "Scoring"), "scoring"),
)


def _latex_inline(text: str) -> str:
    """Inline LaTeX (no math) -> HTML; ``text`` is already HTML-escaped."""
    for _ in range(3):  # nested commands
        text = re.sub(r"\\textbf\{([^{}]*)\}", r"<b>\1</b>", text)
        text = re.sub(r"\\(?:textit|emph)\{([^{}]*)\}", r"<i>\1</i>", text)
        text = re.sub(r"\\(?:texttt|t)\{([^{}]*)\}", r"<tt>\1</tt>", text)
        text = re.sub(r"\\underline\{([^{}]*)\}", r"<u>\1</u>", text)
        text = re.sub(r"\\(?:tiny|scriptsize|small|normalsize|large|Large|LARGE|huge|Huge)\{([^{}]*)\}", r"\1", text)
    text = text.replace("&lt;&lt;", "«").replace("&gt;&gt;", "»")
    text = text.replace("---", "—").replace("--", "–").replace("~", "&nbsp;")
    text = re.sub(r"\\\\(\s*)", r"<br>\1", text)
    return re.sub(r"\\([{}_&%#$])", r"\1", text)


def latex_to_html(src: str) -> str:
    """A small LaTeX -> HTML converter for Polygon statement sections.

    Math stays as ``$...$`` (converted to scripts later); handles paragraphs,
    text formatting, itemize/enumerate, lstlisting/verbatim, tabular, center
    and \\includegraphics. Anything else is left as text.
    """
    stash: list[str] = []

    def keep(fragment: str) -> str:
        stash.append(fragment)
        return f"\x00{len(stash) - 1}\x00"

    src = src.replace("\r\n", "\n")
    src = re.sub(r"\\begin\{(lstlisting|verbatim)\}(?:\[[^\]]*\])?\n?(.*?)\\end\{\1\}",
                 lambda m: keep(f"<pre>{html.escape(m.group(2).rstrip())}</pre>"), src, flags=re.S)
    src = re.sub(r"\\verb(.)(.*?)\1", lambda m: keep(f"<tt>{html.escape(m.group(2))}</tt>"), src)
    # math is kept verbatim (escaped later together with the text it lives in)
    src = re.sub(r"\$\$.+?\$\$|\$[^$]+?\$", lambda m: keep(html.escape(m.group(0), quote=False)), src, flags=re.S)
    src = re.sub(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}",
                 lambda m: keep(f'<img src="{html.escape(m.group(1))}">'), src)

    def table(m: re.Match) -> str:
        rows = [r.replace("\\hline", "").strip() for r in m.group(1).split("\\\\")]
        out = []
        for row in rows:
            if row:
                cells = "".join(f"<td>{_latex_inline(html.escape(c.strip(), quote=False))}</td>"
                                for c in row.split("&"))
                out.append(f"<tr>{cells}</tr>")
        return keep(f'<table class="bordertable">{"".join(out)}</table>')

    src = re.sub(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}", table, src, flags=re.S)

    def listing(m: re.Match) -> str:
        tag = "ol" if m.group(1) == "enumerate" else "ul"
        items = [i.strip() for i in re.split(r"\\item\b", m.group(2)) if i.strip()]
        body = "".join(f"<li>{_latex_inline(html.escape(i, quote=False))}</li>" for i in items)
        return keep(f"<{tag}>{body}</{tag}>")

    for _ in range(2):  # one level of nesting
        src = re.sub(r"\\begin\{(itemize|enumerate)\}(.*?)\\end\{\1\}", listing, src, flags=re.S)
    src = re.sub(r"\\begin\{center\}(.*?)\\end\{center\}",
                 lambda m: keep(f'<div style="text-align: center">{latex_to_html(m.group(1))}</div>'), src,
                 flags=re.S)

    def paragraph(text: str) -> str:
        whole = re.fullmatch(r"\x00(\d+)\x00", text)
        if whole and re.match(r"<(ul|ol|pre|table|div)\b", stash[int(whole.group(1))]):
            return text  # a block of its own: no <p> around it
        return f"<p>{_latex_inline(html.escape(text, quote=False))}</p>"

    body = "".join(paragraph(p.strip()) for p in re.split(r"\n\s*\n", src) if p.strip())
    for _ in range(3):  # stashed fragments may contain stashed fragments
        body = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], body)
    return body


def from_latex(props: dict, files: dict[str, bytes], base_dir: str, warnings: list[str],
               package: PolygonPackage) -> tuple[str, str, str]:
    """(title, html, text) from ``problem-properties.json``."""
    russian = props.get("language", "russian") != "english"
    parts = ['<div class="problem-statement">']
    seconds = package.time_limit_ms / 1000
    megabytes = package.memory_limit_bytes // (1024 * 1024)
    tl = f"{seconds:g} {'секунда' if seconds == 1 else 'секунды'}" if russian else f"{seconds:g} seconds"
    parts.append(
        '<div class="header">'
        f'<div class="time-limit"><div class="property-title">'
        f'{"ограничение по времени на тест" if russian else "time limit per test"}</div>{tl}</div>'
        f'<div class="memory-limit"><div class="property-title">'
        f'{"ограничение по памяти на тест" if russian else "memory limit per test"}</div>'
        f'{megabytes} {"мегабайт" if russian else "megabytes"}</div></div>'
    )
    for key, titles, cls in _LATEX_SECTIONS:
        value = (props.get(key) or "").strip()
        if not value:
            continue
        heading = f'<div class="section-title">{titles[0 if russian else 1]}</div>' if titles else ""
        parts.append(f'<div class="{cls}">{heading}{latex_to_html(value)}</div>')
    samples = props.get("sampleTests") or []
    if samples:
        rows = []
        for sample in samples:
            rows.append(
                '<div class="sample-test">'
                f'<div class="input"><div class="title">{"Входные данные" if russian else "Input"}</div>'
                f'<pre>{html.escape(sample.get("input") or "")}</pre></div>'
                f'<div class="output"><div class="title">{"Выходные данные" if russian else "Output"}</div>'
                f'<pre>{html.escape(sample.get("output") or "")}</pre></div></div>'
            )
        parts.append('<div class="sample-tests"><div class="section-title">'
                     f'{"Примеры" if russian else "Examples"}</div>{"".join(rows)}</div>')
    notes = (props.get("notes") or "").strip()
    if notes:
        parts.append(f'<div class="note"><div class="section-title">{"Примечание" if russian else "Note"}</div>'
                     f"{latex_to_html(notes)}</div>")
    parts.append("</div>")
    soup = BeautifulSoup("".join(parts), "html.parser")
    root = soup.find("div", class_="problem-statement")
    assert root is not None
    _sanitize(soup, root)
    _inline_images(root, files, base_dir, warnings)
    _convert_math(soup, _TEX_MATH_RE)
    _unescape_dollars(root)
    _prefix_classes(root)
    return (props.get("name") or "").strip(), str(root), to_text(root)


# --------------------------------------------------------------------------- entry point
def build_statement(package: PolygonPackage, warnings: list[str] | None = None) -> Statement:
    """The NlogN statement of a parsed package; :class:`EjudgeError` when it has none."""
    warnings = warnings if warnings is not None else []
    files = package.statement_files
    for lang in _html_languages(files):
        base = f".html/{lang}"
        title, body, text = from_polygon_html(files[f"{base}/problem.html"], files, base, warnings)
        return Statement(title or package.name(lang, *LANGUAGES), body, text, lang, "html")

    langs = sorted({k.split("/")[0] for k in files if k.endswith("/problem-properties.json")})
    for lang in [*[x for x in LANGUAGES if x in langs], *[x for x in langs if x not in LANGUAGES]]:
        try:
            props = json.loads(files[f"{lang}/problem-properties.json"].decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            warnings.append(f"problem-properties.json ({lang}) не разбирается: {e}")
            continue
        title, body, text = from_latex(props, files, lang, warnings, package)
        return Statement(title or package.name(lang, *LANGUAGES), body, text, lang, "latex")
    raise EjudgeError("в пакете нет условия (ни HTML, ни problem-properties.json): "
                      "добавьте условие в Polygon и пересоберите пакет")
