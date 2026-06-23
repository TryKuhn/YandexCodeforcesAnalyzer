"""Unit tests for build-error attribution (services.build.error_parser)."""
import pytest

from api.user.gpt.services.build import error_parser as ep


def test_filename_mention_maps_to_type():
    assert ep.parse_offending_file("checker.cpp:12: error: bad") == "checker"


def test_path_line_marker():
    assert ep.parse_offending_file("/tmp/validator.cpp:7: warning") == "validator"


def test_phase_marker_validation():
    assert ep.parse_offending_file("validation failed on test 3") == "validator"


def test_phase_marker_generator_crash():
    assert ep.parse_offending_file("generator crashed unexpectedly") == "generator"


def test_applicable_filter_rejects_outside_set():
    assert ep.parse_offending_file("interactor crashed",
                                   applicable=["validator", "checker"]) is None


def test_empty_log_returns_none():
    assert ep.parse_offending_file("") is None
    assert ep.parse_offending_file("nothing relevant here") is None


@pytest.mark.asyncio
async def test_resolve_uses_deterministic_first(monkeypatch):
    called = {"llm": False}

    async def fake_classify(log, applicable):
        called["llm"] = True
        return None

    monkeypatch.setattr(ep, "classify_offending_file", fake_classify)
    got = await ep.resolve_offending_file("checker.cpp:1: error", ["checker"])
    assert got == "checker" and called["llm"] is False


@pytest.mark.asyncio
async def test_resolve_falls_back_to_classifier(monkeypatch):
    async def fake_classify(log, applicable):
        return "generator"

    monkeypatch.setattr(ep, "classify_offending_file", fake_classify)
    got = await ep.resolve_offending_file("totally opaque log", ["generator"])
    assert got == "generator"


@pytest.mark.asyncio
async def test_classify_offending_file_parses_llm(stub_llm):
    stub_llm(ask={"file_type": "checker"})
    assert await ep.classify_offending_file("log", ["checker", "validator"]) == "checker"


@pytest.mark.asyncio
async def test_classify_offending_file_rejects_outside_set(stub_llm):
    stub_llm(ask={"file_type": "scorer"})
    assert await ep.classify_offending_file("log", ["checker"]) is None
