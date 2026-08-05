"""Limit construction and defaults."""

import dataclasses

import pytest

from app.sandbox.limits import RunLimits


def test_rejects_nonsense_limits():
    with pytest.raises(ValueError):
        RunLimits(cpu_time_ms=0, memory_kb=1024)
    with pytest.raises(ValueError):
        RunLimits(cpu_time_ms=1000, memory_kb=0)
    with pytest.raises(ValueError):
        RunLimits(cpu_time_ms=1000, memory_kb=1024, max_processes=0)


def test_wall_time_defaults_to_double_the_cpu_limit():
    limits = RunLimits(cpu_time_ms=1000, memory_kb=1024)
    assert limits.effective_wall_time_ms == 2000


def test_explicit_wall_time_wins():
    limits = RunLimits(cpu_time_ms=1000, memory_kb=1024, wall_time_ms=5000)
    assert limits.effective_wall_time_ms == 5000


def test_from_problem_converts_megabytes_to_kilobytes():
    limits = RunLimits.from_problem(time_limit_ms=2000, memory_limit_mb=256)
    assert limits.cpu_time_ms == 2000
    assert limits.memory_kb == 256 * 1024


def test_multiplier_gives_slower_languages_a_fair_limit():
    # Python needs roughly triple the time of C++ for the same algorithm.
    limits = RunLimits.from_problem(time_limit_ms=1000, memory_limit_mb=256, tl_multiplier=3.0)
    assert limits.cpu_time_ms == 3000


def test_defaults_are_the_strict_ones():
    limits = RunLimits(cpu_time_ms=1000, memory_kb=1024)
    # A single process by default is what stops fork bombs.
    assert limits.max_processes == 1
    assert limits.output_kb > 0
    assert limits.extra_time_ms > 0


def test_limits_are_immutable():
    limits = RunLimits(cpu_time_ms=1000, memory_kb=1024)
    with pytest.raises(dataclasses.FrozenInstanceError):
        limits.cpu_time_ms = 5000  # type: ignore[misc]
