"""Meta parsing and outcome classification."""

import pytest

from app.sandbox import RunStatus, build_result, classify, parse_meta
from app.sandbox.limits import RunLimits

LIMITS = RunLimits(cpu_time_ms=1000, memory_kb=262144, wall_time_ms=3000)


def test_parses_key_value_lines():
    fields = parse_meta("time:0.052\nmax-rss:1234\nstatus:RE\n")
    assert fields == {"time": "0.052", "max-rss": "1234", "status": "RE"}


def test_keeps_colons_inside_message():
    fields = parse_meta("message:Caught fatal signal 11: segfault\n")
    assert fields["message"] == "Caught fatal signal 11: segfault"


def test_ignores_blank_and_malformed_lines():
    fields = parse_meta("\n  \ngarbage\ntime:0.1\n")
    assert fields == {"time": "0.1"}


def test_successful_run_is_ok():
    meta = "time:0.052\ntime-wall:0.061\nmax-rss:2048\ncg-mem:4096\nexitcode:0\n"
    result = build_result(meta, LIMITS)
    assert result.status is RunStatus.OK
    assert result.ok
    assert result.cpu_time_ms == 52
    assert result.wall_time_ms == 61
    # the run's own peak, not the cgroup total that still holds the compiler
    assert result.memory_kb == 2048


def test_nonzero_exit_is_runtime_error():
    result = build_result("time:0.01\nexitcode:1\nstatus:RE\n", LIMITS)
    assert result.status is RunStatus.RUNTIME_ERROR
    assert result.exit_code == 1


def test_segfault_is_runtime_error_with_signal():
    meta = "time:0.01\nexitsig:11\nstatus:SG\nmessage:Caught fatal signal 11\n"
    result = build_result(meta, LIMITS)
    assert result.status is RunStatus.RUNTIME_ERROR
    assert result.signal == 11


def test_timeout_status_is_time_limit():
    result = build_result("time:1.100\nstatus:TO\nmessage:Time limit exceeded\n", LIMITS)
    assert result.status is RunStatus.TIME_LIMIT


def test_reaching_cpu_limit_is_time_limit_even_without_status():
    # isolate may kill during extra-time and report no status at all.
    result = build_result("time:1.000\ntime-wall:1.2\nexitcode:0\n", LIMITS)
    assert result.status is RunStatus.TIME_LIMIT


def test_wall_clock_overrun_is_time_limit():
    # Sleeping burns no CPU, so only the wall limit catches it.
    result = build_result("time:0.002\ntime-wall:3.500\nexitcode:0\n", LIMITS)
    assert result.status is RunStatus.TIME_LIMIT


def test_oom_kill_is_memory_limit_not_runtime_error():
    # an OOM kill also looks like SIGKILL, so memory must win or every MLE reads as RE
    meta = "time:0.4\ncg-mem:262144\ncg-oom-killed:1\nexitsig:9\nstatus:SG\n"
    result = build_result(meta, LIMITS)
    assert result.status is RunStatus.MEMORY_LIMIT


def test_high_cgroup_usage_without_a_kill_is_not_mle():
    # the box is shared with the compiler, so cg-mem alone must never mean MLE
    result = build_result("time:0.4\ncg-mem:262144\nmax-rss:2048\nexitcode:0\n", LIMITS)
    assert result.status is RunStatus.OK


def test_output_limit_signal_is_not_runtime_error():
    result = build_result("time:0.1\nexitsig:25\nstatus:SG\n", LIMITS)
    assert result.status is RunStatus.OUTPUT_LIMIT


def test_isolate_internal_error_is_not_blamed_on_the_program():
    result = build_result("status:XX\nmessage:Cannot create cgroup\n", LIMITS)
    assert result.status is RunStatus.INTERNAL_ERROR


def test_falls_back_to_cgroup_memory_when_max_rss_missing():
    result = build_result("time:0.1\ncg-mem:5000\nexitcode:0\n", LIMITS)
    assert result.memory_kb == 5000


def test_garbage_values_do_not_crash():
    result = build_result("time:not-a-number\nexitcode:oops\n", LIMITS)
    assert result.cpu_time_ms == 0
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "meta,expected",
    [
        ("exitcode:0\n", RunStatus.OK),
        ("status:TO\n", RunStatus.TIME_LIMIT),
        ("cg-oom-killed:1\n", RunStatus.MEMORY_LIMIT),
        ("cg-mem:999999\nexitcode:0\n", RunStatus.OK),
        ("status:XX\n", RunStatus.INTERNAL_ERROR),
    ],
)
def test_classification_table(meta, expected):
    assert classify(parse_meta(meta), LIMITS) is expected


def test_describe_is_human_readable():
    result = build_result("time:0.5\nmax-rss:1024\nexitsig:11\nstatus:SG\n", LIMITS)
    assert "RE" in result.describe()
    assert "signal=11" in result.describe()
