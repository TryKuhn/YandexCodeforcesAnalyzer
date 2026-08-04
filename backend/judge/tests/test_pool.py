"""Box id leasing."""

import asyncio

import pytest

from app.sandbox.pool import BoxCorrupted, BoxPool


def test_rejects_invalid_ranges():
    with pytest.raises(ValueError):
        BoxPool(size=0)
    with pytest.raises(ValueError):
        BoxPool(size=10, first_id=995)  # would run past box id 999


async def test_lease_returns_the_box_afterwards():
    pool = BoxPool(size=2)
    async with pool.lease() as box_id:
        assert box_id in (0, 1)
        assert pool.available == 1
    assert pool.available == 2


async def test_leases_are_exclusive():
    pool = BoxPool(size=2)
    async with pool.lease() as first, pool.lease() as second:
        assert first != second
        assert pool.available == 0


async def test_waits_when_every_box_is_busy():
    pool = BoxPool(size=1)
    order = []

    async def worker(name):
        async with pool.lease():
            order.append(f"{name}-start")
            await asyncio.sleep(0.01)
            order.append(f"{name}-end")

    await asyncio.gather(worker("a"), worker("b"))

    # The second worker must not start before the first released the box.
    assert order in (
        ["a-start", "a-end", "b-start", "b-end"],
        ["b-start", "b-end", "a-start", "a-end"],
    )


async def test_box_returns_to_the_pool_after_an_error():
    pool = BoxPool(size=1)
    with pytest.raises(RuntimeError):
        async with pool.lease():
            raise RuntimeError("judging blew up")
    # An ordinary failure does not dirty the box.
    assert pool.available == 1
    assert pool.broken == frozenset()


async def test_corrupted_box_is_retired_not_reused():
    pool = BoxPool(size=2)
    with pytest.raises(BoxCorrupted):
        async with pool.lease() as box_id:
            failed = box_id
            raise BoxCorrupted("cleanup failed")

    assert failed in pool.broken
    assert pool.available == 1


async def test_retire_removes_a_box_from_circulation():
    pool = BoxPool(size=2)
    pool.retire(0)
    assert 0 in pool.broken


def test_first_id_offsets_the_range():
    pool = BoxPool(size=3, first_id=100)
    assert pool.size == 3
    assert pool.available == 3
