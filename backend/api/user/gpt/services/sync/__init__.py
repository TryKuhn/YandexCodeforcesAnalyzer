"""Immediate-push sync layer: writes a generated artifact to our DB and to
Polygon in one step.

Every incremental edit (manual or AI) goes through here so the local
``TaskGeneratedFile`` rows and the Polygon working copy never drift apart. This
layer owns *only* the orchestration of "upsert locally + push to Polygon"; the
raw Polygon API calls live in ``api.user.polygon`` and the file taxonomy lives
in ``api.user.gpt.services.files.file_registry``.
"""
from api.user.gpt.services.sync.file_sync import (ensure_problem, sync_file,
                                                  sync_files)
from api.user.gpt.services.sync.settings_sync import (sync_settings, sync_tags)
from api.user.gpt.services.sync.statement_sync import sync_statement

__all__ = [
    "ensure_problem",
    "sync_file",
    "sync_files",
    "sync_statement",
    "sync_settings",
    "sync_tags",
]
