"""Unit tests for models/task/session.py — enums and TaskSession defaults."""
from datetime import datetime

import pytest

from models.task.session import PipelineStage, ProblemType, TaskSession


def test_pipeline_stage_values():
    assert PipelineStage.STATEMENT == "statement"
    assert PipelineStage.DONE == "done"
    assert PipelineStage.FAILED == "failed"
    # str-enum: comparable to plain strings
    assert PipelineStage.UPLOADING.value == "uploading"
    assert {s.value for s in PipelineStage} == {
        "statement", "files_review", "uploading", "fixing_errors",
        "building_package", "done", "failed",
    }


def test_problem_type_values():
    assert ProblemType.REGULAR == "regular"
    assert ProblemType.INTERACTIVE == "interactive"
    assert ProblemType.OUTPUT_ONLY == "output_only"


@pytest.mark.asyncio
async def test_task_session_defaults_persist(db, user):
    now = datetime(2026, 1, 1)
    s = TaskSession(
        id="s-defaults",
        user_id=user.id,
        model="anthropic/claude-opus-4.8",
        system_prompt="",
        created_at=now,
        updated_at=now,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)

    # JSON/string column defaults applied by SQLAlchemy
    assert s.history == []
    assert s.problem_type == ProblemType.REGULAR
    assert s.stage == PipelineStage.STATEMENT
    assert s.progress == {"status": "idle"}
    assert s.ai_fix_attempts == {}
    assert s.chat_log == []


@pytest.mark.asyncio
async def test_task_session_fixture_round_trips(task_session):
    # The shared fixture builds a REGULAR session; sanity-check it persisted.
    assert task_session.id == "sess-1"
    assert task_session.problem_type == ProblemType.REGULAR
    assert task_session.polygon_problem_id == 555
