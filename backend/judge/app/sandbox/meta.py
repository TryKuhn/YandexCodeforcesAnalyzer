"""Parsing of the isolate meta file, where TLE and MLE are decided."""

from .limits import RunLimits
from .result import RunResult, RunStatus

# raised on writing past the file size limit, an output overrun rather than RE
SIGXFSZ = 25

_ISOLATE_TIMEOUT = "TO"
_ISOLATE_SIGNAL = "SG"
_ISOLATE_RUNTIME = "RE"
_ISOLATE_INTERNAL = "XX"


def parse_meta(text: str) -> dict[str, str]:
    """Turn raw meta-file text into a flat dict, keeping unknown keys."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        # split once only, "message" carries colons of its own
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def _seconds_to_ms(raw: str | None) -> int:
    if not raw:
        return 0
    try:
        return round(float(raw) * 1000)
    except ValueError:
        return 0


def _to_int(raw: str | None) -> int:
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0


def classify(fields: dict[str, str], limits: RunLimits) -> RunStatus:
    """Decide how the process ended, order matters."""
    status = fields.get("status", "")
    signal = _to_int(fields.get("exitsig"))

    # OOM also looks like a SIGKILL, so it must be checked before signals.
    # Only the kill flag is trusted: cg-mem is the cgroup peak and still holds
    # the compiler's footprint, which would turn every run into a false MLE.
    if _to_int(fields.get("cg-oom-killed")) == 1:
        return RunStatus.MEMORY_LIMIT

    if signal == SIGXFSZ:
        return RunStatus.OUTPUT_LIMIT

    if status == _ISOLATE_TIMEOUT:
        return RunStatus.TIME_LIMIT
    # isolate may kill during extra-time and report no status at all
    if _seconds_to_ms(fields.get("time")) >= limits.cpu_time_ms > 0:
        return RunStatus.TIME_LIMIT
    wall_limit = limits.effective_wall_time_ms
    if _seconds_to_ms(fields.get("time-wall")) >= wall_limit > 0:
        return RunStatus.TIME_LIMIT

    if status == _ISOLATE_INTERNAL:
        return RunStatus.INTERNAL_ERROR

    if status in (_ISOLATE_SIGNAL, _ISOLATE_RUNTIME):
        return RunStatus.RUNTIME_ERROR
    if _to_int(fields.get("exitcode")) != 0:
        return RunStatus.RUNTIME_ERROR

    return RunStatus.OK


def build_result(text: str, limits: RunLimits) -> RunResult:
    """Parse a meta file and classify it in one step."""
    fields = parse_meta(text)
    signal = _to_int(fields.get("exitsig"))
    return RunResult(
        status=classify(fields, limits),
        exit_code=_to_int(fields.get("exitcode")),
        signal=signal or None,
        cpu_time_ms=_seconds_to_ms(fields.get("time")),
        wall_time_ms=_seconds_to_ms(fields.get("time-wall")),
        # max-rss is the run's own peak; cg-mem would include the compiler that
        # shared this box, so it is only a fallback
        memory_kb=_to_int(fields.get("max-rss")) or _to_int(fields.get("cg-mem")),
        message=fields.get("message", ""),
    )
