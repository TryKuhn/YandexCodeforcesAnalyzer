"""Detect an intentionally-declined solution generation.

An incorrect-solution prompt is told to return ``SKIP: <reason>`` instead of code
when it cannot honestly guarantee the tagged verdict with a genuine algorithm.
The caller then omits that solution (never uploading one that would fail Polygon's
tag verification and churn the repair loop) and tells the user why.
"""
from api.user.gpt.services.prompts.base import SKIP_MARKER

_DEFAULT_REASON = ("не удалось придумать решение, которое гарантированно "
                   "получает нужный вердикт")


def parse_skip(text: str) -> str | None:
    """Return the skip reason if the generation declined, else ``None``.

    Recognises a leading ``SKIP`` marker (case-insensitive), tolerating an
    optional ``:``/dash separator before the reason. Real source files never
    start with this marker, so false positives are not a concern.
    """
    # The prompt shows the marker as `SKIP: ...` and models tend to copy the
    # backticks (or bold it) - such a reply must still count as a skip, not be
    # uploaded as source code.
    stripped = (text or "").strip().strip("`*\"' ").strip()
    if not stripped.upper().startswith(SKIP_MARKER.upper()):
        return None
    # the wrapping may sit right after the marker too: "`SKIP`: reason"
    reason = stripped[len(SKIP_MARKER):].lstrip(" :\t—-`*\"'").strip()
    # Keep it to the first line — the model may add stray trailing text.
    reason = reason.splitlines()[0].strip().strip("`*\"' ") if reason else ""
    return reason or _DEFAULT_REASON
