"""A Polygon-generated HTML statement (trimmed, but with the real structure)."""
import base64
import json

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

PROBLEM_HTML = """<!DOCTYPE html>
<html><head>
<meta content="text/html; charset=UTF-8" http-equiv="Content-Type"/>
<link href="problem-statement.css" rel="stylesheet" type="text/css"/>
<title>Сумма</title>
<script type="text/x-mathjax-config">MathJax.Hub.Config({tex2jax: {inlineMath: [['$$$','$$$']]}});</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.5/MathJax.js" type="text/javascript"></script>
</head><body>
<div class="problem-statement">
<div class="header">
<div class="title">A. Сумма</div>
<div class="time-limit"><div class="property-title">ограничение по времени на тест</div>1 секунда</div>
<div class="memory-limit"><div class="property-title">ограничение по памяти на тест</div>256 мегабайт</div>
<div class="input-file"><div class="property-title">ввод</div>стандартный ввод</div>
<div class="output-file"><div class="property-title">вывод</div>стандартный вывод</div>
</div>
<div><p>Даны числа $$$a$$$ и $$$b$$$ ($$$1 \\le a, b &lt; 10^9$$$). Найдите <b>сумму</b>.</p>
<p>$$$$$$a + b = c$$$$$$</p>
<center><img class="tex-graphics" src="pic.png" style="max-width: 100.0%;max-height: 100.0%;"/></center>
<p onclick="alert(1)">Стоимость \\$5.</p></div>
<div class="input-specification"><div class="section-title">Входные данные</div><p>Два числа $$$a$$$ и $$$b$$$.</p></div>
<div class="output-specification"><div class="section-title">Выходные данные</div><p>Одно число.</p></div>
<div class="sample-tests"><div class="section-title">Примеры</div>
<div class="sample-test"><div class="input"><div class="title">Входные данные</div><pre class="content">1 2
</pre></div><div class="output"><div class="title">Выходные данные</div><pre class="content">3
</pre></div></div></div>
<div class="note"><div class="section-title">Примечание</div><p>Сумма $$$1 + 2 = 3$$$.</p><script>evil()</script></div>
</div>
</body></html>
"""

PROPERTIES = {
    "name": "Сумма",
    "legend": "Даны числа $a$ и $b$ ($1 \\le a, b \\le 10^9$). Найдите \\textbf{сумму}.\n\n"
              "\\begin{itemize}\n\\item первое;\n\\item второе.\n\\end{itemize}\n\n"
              "$$a + b$$\n\n\\includegraphics{pic.png}",
    "input": "Два числа --- <<a>> и <<b>>.",
    "output": "Одно число.",
    "notes": "\\begin{lstlisting}\nprint(1 + 2)\n\\end{lstlisting}",
    "sampleTests": [{"input": "1 2\n", "output": "3\n"}],
    "language": "russian",
}

HTML_STATEMENTS = {".html/russian/problem.html": PROBLEM_HTML, ".html/russian/pic.png": PNG}
LATEX_STATEMENTS = {"russian/problem-properties.json": json.dumps(PROPERTIES), "russian/pic.png": PNG}
