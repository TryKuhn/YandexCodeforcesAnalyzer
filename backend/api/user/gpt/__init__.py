"""GPT package entry point.

Importing the routes package registers every endpoint (sessions, imports,
statement, files, build, chat) on gpt_router as a side effect.
"""
from api.user.gpt.base_gpt import gpt_router

from api.user.gpt import routes

__all__ = ["routes", "gpt_router"]
