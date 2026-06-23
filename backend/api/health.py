"""Health-check endpoint."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Liveness probe returning a static ok status."""
    return {"status": "ok"}
