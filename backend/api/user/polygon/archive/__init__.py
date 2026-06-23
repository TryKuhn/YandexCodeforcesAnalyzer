"""Olympiad-archive import package: exposes the archive import router."""
from api.user.polygon.archive.router import router as archive_router

__all__ = ["archive_router"]
