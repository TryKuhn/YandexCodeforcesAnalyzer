import pytest

from authoring.llm.client import LLMError, parse_json, strip_fences
from authoring.llm.protocol import (
    FileEdit,
    GroupsEdit,
    LimitsEdit,
    SampleEdit,
    ScriptEdit,
    StandardChecker,
    StatementEdit,
    TagsEdit,
    parse,
    single_file,
)

ANSWER = r'''
Some preamble the model should not have written.
<reply>
Исправил генератор: теперь $n \le 10^5$.
</reply>
<file role="generator" name="gen.cpp">
#include "testlib.h"
#include <bits/stdc++.h>
int main(int argc, char* argv[]) {
    registerGen(argc, argv, 1);
    printf("%d\n", rnd.next(1, 10));
    if (1 < 2 && "x" != "</fil") {}
}
</file>
<file role="solution" name="wa.cpp" tag="wa">int main() {}</file>
<statement lang="russian" field="legend">Дано $n$ чисел \textbf{a}.</statement>
<script>
gen 1 > $
</script>
<limits time_limit="2000" memory_limit="512"/>
<tags>dp, greedy
math</tags>
<checker standard="ncmp.cpp"/>
<sample>1 2
</sample>
<groups>{"groups": [{"name": "1"}]}</groups>
'''


def test_parse_all_blocks():
    parsed = parse(ANSWER)
    assert parsed.reply == r"Исправил генератор: теперь $n \le 10^5$."
    kinds = [type(e) for e in parsed.edits]
    assert kinds == [FileEdit, FileEdit, StatementEdit, ScriptEdit, LimitsEdit, TagsEdit, StandardChecker,
                     SampleEdit, GroupsEdit]
    gen = parsed.edits[0]
    assert isinstance(gen, FileEdit)
    assert gen.role == "generator" and gen.name == "gen.cpp" and gen.target == "generator"
    assert '"x" != "</fil"' in gen.content and gen.content.endswith("}\n")
    wa = parsed.edits[1]
    assert isinstance(wa, FileEdit) and wa.tag == "WA" and wa.target == "solution"
    st = parsed.edits[2]
    assert isinstance(st, StatementEdit) and st.field == "legend" and st.content.startswith("Дано")
    assert parsed.edits[4] == LimitsEdit(2000, 512)
    assert parsed.edits[5] == TagsEdit(["dp", "greedy", "math"])
    assert parsed.edits[6] == StandardChecker("std::ncmp.cpp")
    assert parsed.edits[7] == SampleEdit("1 2\n")
    assert parsed.edits[8] == GroupsEdit({"groups": [{"name": "1"}]})
    assert parsed.warnings == []


def test_parse_rejects_bad_blocks():
    parsed = parse(
        '<file role="hacker" name="x.cpp">x</file>'
        '<file role="generator" name="../etc/passwd">x</file>'
        '<file role="generator" name="g.cpp">   </file>'
        '<statement field="history">x</statement>'
        '<file role="solution" name="s.cpp" tag="ZZ">int main(){}</file>'
        "<groups>{not json}</groups>"
    )
    assert len(parsed.warnings) == 6
    assert len(parsed.edits) == 1
    edit = parsed.edits[0]
    assert isinstance(edit, FileEdit) and edit.tag is None


def test_parse_strips_inner_fences():
    parsed = parse('<file role="validator" name="v.cpp">\n```cpp\nint main() {}\n```\n</file>')
    edit = parsed.edits[0]
    assert isinstance(edit, FileEdit)
    assert edit.content == "int main() {}\n"


def test_plain_text_becomes_reply():
    assert parse("Просто ответ").reply == "Просто ответ"


def test_single_file_fallbacks():
    assert single_file("```cpp\nint main(){}\n```", role="validator").content == "int main(){}\n"
    edit = single_file('<reply>x</reply><file role="checker" name="c.cpp">code</file>', role="checker")
    assert edit.name == "c.cpp"
    with pytest.raises(LLMError):
        single_file("   ", role="checker")


def test_parse_json_tolerates_prose():
    assert parse_json('Вот план:\n```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('ok {"a": {"b": 2}} done') == {"a": {"b": 2}}
    with pytest.raises(LLMError):
        parse_json("no json here")
    with pytest.raises(LLMError):
        parse_json("[1, 2]")


def test_strip_fences():
    assert strip_fences("```\nx\n```") == "x"
    assert strip_fences("plain") == "plain"


def test_testlib_include_is_quoted():
    edit = parse('<file role="checker" name="c.cpp">#include <testlib.h>\nint main(){}</file>').edits[0]
    assert isinstance(edit, FileEdit) and edit.content.startswith('#include "testlib.h"')
    assert single_file("#include < testlib.h >\nx", role="validator").content.startswith('#include "testlib.h"')


def test_single_quotes_truncation_and_checker_suffix():
    parsed = parse("<file role='validator' name='v.cpp'>int main(){}</file><checker standard=\"wcmp\"/>"
                   '<file role="generator" name="g.cpp">int main() { // cut by max_tokens')
    assert [type(e) for e in parsed.edits] == [FileEdit, StandardChecker]
    assert parsed.edits[1] == StandardChecker("std::wcmp.cpp")
    assert any("оборвана" in w for w in parsed.warnings)
    assert parse('<limits time_limit="1e999"/>').edits == []
