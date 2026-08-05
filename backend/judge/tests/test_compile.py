"""Compiling a submission inside the sandbox."""

from app.languages import CPP, PYTHON, Language, compile_source
from app.sandbox.result import RunResult, RunStatus

from .fakes import FakeSession


async def test_source_lands_in_the_box_under_the_expected_name():
    session = FakeSession()
    await compile_source(session, CPP, b"int main(){}")
    assert session.files["main.cpp"] == b"int main(){}"


async def test_successful_compilation():
    session = FakeSession([RunResult(status=RunStatus.OK)])
    result = await compile_source(session, CPP, b"int main(){}")
    assert result.ok
    assert not result.compile_error


async def test_compiler_writes_its_binary_into_the_box():
    session = FakeSession()
    result = await compile_source(session, CPP, b"int main(){}")
    # isolate's box is writable by default, so -o lands next to the source
    assert "-o" in session.runs[0]["argv"]
    assert result.binary_name in session.runs[0]["argv"]


async def test_compiler_output_is_captured_for_the_contestant():
    session = FakeSession([RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)])
    session.files["compile.log"] = b"main.cpp:1:1: error: expected declaration"
    result = await compile_source(session, CPP, b"garbage")
    assert result.compile_error
    assert "expected declaration" in result.log


async def test_compile_error_is_not_an_internal_error():
    session = FakeSession([RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)])
    result = await compile_source(session, CPP, b"garbage")
    assert not result.internal_error


async def test_broken_sandbox_is_flagged_separately():
    # a failing sandbox must not be reported as the contestant's compile error
    session = FakeSession([RunResult(status=RunStatus.INTERNAL_ERROR, message="isolate failed")])
    result = await compile_source(session, CPP, b"int main(){}")
    assert result.internal_error
    assert not result.compile_error


async def test_compiler_timeout_is_explained():
    session = FakeSession([RunResult(status=RunStatus.TIME_LIMIT)])
    result = await compile_source(session, CPP, b"template bomb")
    assert result.compile_error
    assert "timed out" in result.log


async def test_compiler_out_of_memory_is_explained():
    session = FakeSession([RunResult(status=RunStatus.MEMORY_LIMIT)])
    result = await compile_source(session, CPP, b"template bomb")
    assert "memory" in result.log


async def test_huge_compiler_log_is_truncated():
    session = FakeSession([RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)])
    session.files["compile.log"] = b"x" * (200 * 1024)
    result = await compile_source(session, CPP, b"garbage")
    assert len(result.log) <= 64 * 1024


async def test_python_is_syntax_checked_before_running():
    session = FakeSession()
    await compile_source(session, PYTHON, b"print(1)")
    assert "py_compile" in " ".join(session.runs[0]["argv"])  # type: ignore[arg-type]


async def test_language_without_compilation_skips_the_step():
    lang = Language(id="raw", name="Raw", source_name="main.txt", run_argv=("cat", "main.txt"))
    session = FakeSession()
    result = await compile_source(session, lang, b"hello")
    assert result.ok
    assert session.runs == []


async def test_extra_files_are_placed_in_the_box():
    session = FakeSession()
    await compile_source(session, CPP, b"int main(){}", extra_files={"testlib.h": b"// testlib"})
    assert session.files["testlib.h"] == b"// testlib"


async def test_compilation_gets_its_own_looser_limits():
    session = FakeSession()
    await compile_source(session, CPP, b"int main(){}")
    limits = session.runs[0]["limits"]
    assert limits.cpu_time_ms == CPP.compile_time_ms  # type: ignore[union-attr]
    # g++ forks, so a single-process cap would break the build
    assert limits.max_processes > 1  # type: ignore[union-attr]
