"""Shared types of the Ejudge export."""


class EjudgeError(Exception):
    """An export problem with a message for the user (Russian)."""


def is_configured(settings) -> bool:  # type: ignore[no-untyped-def]
    """SSH access is the minimum; the web part (reload) is optional."""
    return bool(settings.EJUDGE_SSH_HOST and settings.EJUDGE_JUDGES_DIR)
