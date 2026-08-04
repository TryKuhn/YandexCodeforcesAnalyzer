"""Language registry."""

import pytest

from app.languages import (
    CPP,
    PYTHON,
    Language,
    UnknownLanguage,
    all_languages,
    get,
    register,
)


def test_known_languages_are_available():
    ids = {lang.id for lang in all_languages()}
    assert {"cpp", "python"} <= ids


def test_lookup_by_id():
    assert get("cpp") is CPP
    assert get("python") is PYTHON


def test_unknown_language_is_reported_clearly():
    with pytest.raises(UnknownLanguage) as excinfo:
        get("brainfuck")
    assert "brainfuck" in str(excinfo.value)


def test_cpp_compiles_with_o2():
    assert CPP.needs_compilation
    assert "-O2" in CPP.compile_argv
    assert CPP.run_command("main.cpp", "main") == ("./main",)


def test_commands_are_rendered_per_binary():
    # a checker builds beside the solution without overwriting it
    assert CPP.compile_command("checker_main.cpp", "checker") == (
        "g++", "-O2", "-std=c++17", "-o", "checker", "checker_main.cpp",
    )
    assert CPP.source_file("checker") == "checker_main.cpp"
    assert CPP.source_file("main") == "main.cpp"


def test_cpp_has_no_time_handicap():
    assert CPP.tl_multiplier == 1.0


def test_python_gets_a_larger_time_budget():
    # roughly triple, otherwise correct Python solutions fail on a C++ limit
    assert PYTHON.tl_multiplier >= 3.0
    assert PYTHON.ml_multiplier > 1.0


def test_python_is_syntax_checked_so_typos_become_compile_errors():
    assert PYTHON.needs_compilation
    assert "py_compile" in " ".join(PYTHON.compile_argv)


def test_compilation_allows_several_processes():
    # g++ forks cc1plus, a single-process limit would break every build
    assert CPP.compile_processes > 1


def test_new_language_needs_no_change_to_judging_code():
    lang = Language(
        id="test-lang",
        name="Test",
        source_name="main.txt",
        run_argv=("cat", "main.txt"),
    )
    register(lang)
    try:
        assert get("test-lang") is lang
        assert not lang.needs_compilation
    finally:
        from app.languages import registry

        registry._REGISTRY.pop("test-lang", None)


def test_registering_twice_is_rejected():
    with pytest.raises(ValueError):
        register(CPP)


def test_languages_are_immutable():
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        CPP.tl_multiplier = 9.0  # type: ignore[misc]
