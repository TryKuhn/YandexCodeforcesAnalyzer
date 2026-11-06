"""The NlogN statement built from a Polygon package."""
import pytest

from api.user.ejudge.common import EjudgeError
from api.user.ejudge.package import parse_package
from api.user.nlogn.statement import build_statement, latex_to_html
from tests.unit.ejudge.helpers import package_zip
from tests.unit.nlogn.fixtures import HTML_STATEMENTS, LATEX_STATEMENTS

TESTS = [{"sample": True}, {}]


def test_from_polygon_html():
    warnings: list[str] = []
    st = build_statement(parse_package(package_zip(TESTS, statements=HTML_STATEMENTS)), warnings)
    html = st.html
    assert st.source == "html" and st.language == "russian" and st.title == "Сумма"
    assert html.startswith('<div class="task__my-problem-statement">')
    # classes are prefixed like NlogN's own "polygonify" does
    assert 'class="task__my-sample-tests"' in html and 'class="task__my-section-title"' in html
    assert 'class="problem-statement"' not in html
    # the title and standard input/output lines are dropped, limits are kept
    assert "A. Сумма" not in html and "стандартный ввод" not in html and "256 мегабайт" in html
    # formulas -> MathJax script tags, entities decoded inside them
    assert '<script type="math/tex">1 \\le a, b < 10^9</script>' in html
    assert '<script type="math/tex; mode=display">a + b = c</script>' in html
    assert "$$$" not in html
    # an escaped dollar in plain text loses its backslash (MathJax would print it)
    assert "Стоимость $5." in html and "\\$" not in html
    # samples keep their text
    assert "<pre class=\"task__my-content\">1 2\n</pre>" in html
    # images inlined, nothing active left
    assert 'src="data:image/png;base64,' in html
    assert "evil()" not in html and "onclick" not in html and "mathjax-config" not in html
    assert "<link" not in html
    assert not warnings
    assert "$1 \\le a, b < 10^9$" in st.text and "Входные данные" in st.text


def test_latex_fallback_when_package_has_no_html():
    st = build_statement(parse_package(package_zip(TESTS, statements=LATEX_STATEMENTS, time_limit=2000)))
    html = st.html
    assert st.source == "latex" and st.title == "Сумма"
    assert '<script type="math/tex">a</script>' in html
    assert '<script type="math/tex; mode=display">a + b</script>' in html
    assert "<b>сумму</b>" in html and "<li>первое;</li>" in html and "<ul>" in html
    assert "«a»" in html and "—" in html
    assert "<pre>print(1 + 2)</pre>" in html
    assert 'class="task__my-sample-tests"' in html and "<pre>1 2\n</pre>" in html
    assert "2 секунды" in html and 'src="data:image/png;base64,' in html


def test_missing_statement_and_image():
    with pytest.raises(EjudgeError, match="нет условия"):
        build_statement(parse_package(package_zip(TESTS)))
    warnings: list[str] = []
    files = {".html/russian/problem.html": HTML_STATEMENTS[".html/russian/problem.html"]}
    st = build_statement(parse_package(package_zip(TESTS, statements=files)), warnings)
    assert "<img" not in st.html and "pic.png" in warnings[0]


def test_latex_converter_details():
    html = latex_to_html("Код: \\verb|a<b|, $x < y$.\n\n\\begin{tabular}{|c|c|}\\hline 1 & 2 \\\\ \\hline\\end{tabular}")
    assert "<tt>a&lt;b</tt>" in html and "$x &lt; y$" in html
    assert "<table" in html and "<td>1</td><td>2</td>" in html


def test_html_math_styles():
    base = HTML_STATEMENTS[".html/russian/problem.html"]
    # $$$ style: a lone dollar is just a dollar
    html = base.replace("Стоимость \\$5.", "Цена 5$ или 7$.")
    st = build_statement(parse_package(package_zip(TESTS, statements={".html/russian/problem.html": html})))
    assert "Цена 5$ или 7$." in st.html
    # plain TeX dollars when there is no $$$ at all
    tex = base.replace("$$$$$$", "$$").replace("$$$", "$")
    st = build_statement(parse_package(package_zip(TESTS, statements={".html/russian/problem.html": tex})))
    assert '<script type="math/tex">1 \\le a, b < 10^9</script>' in st.html
    assert '<script type="math/tex; mode=display">a + b = c</script>' in st.html
