"""All gpt route packages. Importing each registers its endpoints on gpt_router.

One endpoint per module, grouped by domain:
  sessions/  — session lifecycle
  imports/   — import from Polygon
  statement/ — statement generation & editing
  files/     — technical-file generation & editing
  build/     — upload + package build + progress
  chat/      — two-stage AI chat (added in P3)
"""
from api.user.gpt.routes import (build, chat, files, imports, sessions,
                                 statement)

__all__ = ["sessions", "imports", "statement", "files", "build", "chat"]
