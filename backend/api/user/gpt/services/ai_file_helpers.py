from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai.ai_generated_file import AIGeneratedFile

FILE_NAME_MAP: dict[str, str] = {
    "validator":    "validator.cpp",
    "generator":    "generator.cpp",
    "checker":      "checker.cpp",
    "solution_cpp": "solution.cpp",
    "solution_py":  "solution_python.py",
    "wa_sol":       "wa.cpp",
    "tl_sol":       "tl.cpp",
    "re_sol":       "re.cpp",
    "ml_sol":       "ml.cpp",
    "script":       "script.txt",
}


async def upsert_ai_file(
    db: AsyncSession,
    session_id: str,
    file_type: str,
    content: str,
    *,
    uploaded: bool = False,
) -> None:
    filename = FILE_NAME_MAP.get(file_type, file_type)
    result = await db.execute(
        select(AIGeneratedFile).where(
            AIGeneratedFile.session_id == session_id,
            AIGeneratedFile.file_type == file_type,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.content = content
        existing.filename = filename
        existing.uploaded = uploaded
    else:
        db.add(AIGeneratedFile(
            session_id=session_id,
            filename=filename,
            content=content,
            file_type=file_type,
            uploaded=uploaded,
        ))


async def upsert_all_ai_files(
    db: AsyncSession,
    session_id: str,
    tech_data: dict,
    *,
    uploaded: bool = False,
) -> None:
    for file_type, content in tech_data.items():
        if content:
            await upsert_ai_file(db, session_id, file_type, content, uploaded=uploaded)


async def mark_uploaded(
    db: AsyncSession,
    session_id: str,
    file_type: str,
) -> None:
    await db.execute(
        update(AIGeneratedFile)
        .where(
            AIGeneratedFile.session_id == session_id,
            AIGeneratedFile.file_type == file_type,
        )
        .values(uploaded=True)
    )


async def get_session_files(
    db: AsyncSession,
    session_id: str,
) -> dict[str, AIGeneratedFile]:
    """Returns {file_type: AIGeneratedFile} for all files in the session."""
    result = await db.execute(
        select(AIGeneratedFile).where(AIGeneratedFile.session_id == session_id)
    )
    return {f.file_type: f for f in result.scalars().all()}


async def get_all_file_contents(
    db: AsyncSession,
    session_id: str,
) -> dict[str, str]:
    """Returns {file_type: content} for all files regardless of upload status."""
    files = await get_session_files(db, session_id)
    return {k: v.content for k, v in files.items()}


async def get_uploaded_file_contents(
    db: AsyncSession,
    session_id: str,
) -> dict[str, str]:
    """Returns {file_type: content} only for files confirmed uploaded to Polygon."""
    result = await db.execute(
        select(AIGeneratedFile).where(
            AIGeneratedFile.session_id == session_id,
            AIGeneratedFile.uploaded.is_(True),
        )
    )
    return {f.file_type: f.content for f in result.scalars().all()}
