"""Unit tests for sample-test upload (services.sync.samples_sync)."""
import pytest

from api.user.gpt.services.sync import samples_sync as sm


def _patch_save_test(monkeypatch, fail_indices=()):
    """Record save_test calls; raise for indices listed in ``fail_indices``."""
    calls = []

    async def fake_save_test(**kwargs):
        calls.append(kwargs)
        if kwargs["test_index"] in fail_indices:
            raise RuntimeError("polygon rejected test")

    monkeypatch.setattr(
        "api.user.gpt.services.sync.samples_sync.save_test", fake_save_test
    )
    return calls


@pytest.mark.asyncio
async def test_upload_examples_saves_manual_sample_tests(db, monkeypatch):
    calls = _patch_save_test(monkeypatch)
    examples = [{"input": "1 2", "output": "3"}, {"input": "4 5", "output": "9"}]

    saved = await sm.upload_examples(db, 555, 7, examples)
    assert saved == 2

    # indices are 1..N, marked as statement examples, in the "tests" testset
    assert [c["test_index"] for c in calls] == [1, 2]
    assert all(c["test_use_in_statements"] is True for c in calls)
    assert all(c["testset"] == "tests" for c in calls)
    assert all(c["problem_id"] == 555 and c["user_id"] == 7 for c in calls)
    assert calls[0]["test_input"] == "1 2"


@pytest.mark.asyncio
async def test_upload_examples_skips_empty_input(db, monkeypatch):
    calls = _patch_save_test(monkeypatch)
    examples = [
        {"input": "data"},
        {"input": "   "},   # whitespace-only -> skipped
        {"input": ""},      # empty -> skipped
        None,               # None entry -> skipped
        {"input": "more"},
    ]
    saved = await sm.upload_examples(db, 555, 7, examples)
    assert saved == 2
    # only the two non-empty inputs reached Polygon, re-indexed 1..N starting at
    # the original enumerate index (1-based over the full list)
    inputs = [c["test_input"] for c in calls]
    assert inputs == ["data", "more"]


@pytest.mark.asyncio
async def test_upload_examples_dedups_identical_inputs(db, monkeypatch):
    # Polygon rejects duplicate manual tests ("Test coincides with #..."), so
    # identical inputs (incl. whitespace-different) must be dropped + re-indexed.
    calls = _patch_save_test(monkeypatch)
    examples = [
        {"input": "1 2", "output": "3"},
        {"input": "1  2", "output": "3"},   # same up to whitespace -> dropped
        {"input": "4 5", "output": "9"},
    ]
    saved = await sm.upload_examples(db, 555, 7, examples)
    assert saved == 2
    assert [c["test_index"] for c in calls] == [1, 2]
    assert [c["test_input"] for c in calls] == ["1 2", "4 5"]


@pytest.mark.asyncio
async def test_upload_examples_resilient_to_failure(db, monkeypatch):
    calls = _patch_save_test(monkeypatch, fail_indices={1})
    examples = [{"input": "a"}, {"input": "b"}]
    saved = await sm.upload_examples(db, 555, 7, examples)
    # first failed, second succeeded
    assert saved == 1
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_upload_examples_forwards_group(db, monkeypatch):
    calls = _patch_save_test(monkeypatch)
    await sm.upload_examples(db, 555, 7, [{"input": "a"}], group="samples")
    assert calls[0]["test_group"] == "samples"


@pytest.mark.asyncio
async def test_upload_examples_empty_list_returns_zero(db, monkeypatch):
    calls = _patch_save_test(monkeypatch)
    assert await sm.upload_examples(db, 555, 7, []) == 0
    assert calls == []
