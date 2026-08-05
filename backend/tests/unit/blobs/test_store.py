"""Content-addressed store: dedup, refcounts, roundtrip."""
import hashlib

from sqlalchemy import select

from models.blobs.blob import Blob


async def test_put_stores_bytes_under_their_hash(db, store, s3):
    data = b"hello judge"
    sha = await store.put(db, data)

    assert sha == hashlib.sha256(data).hexdigest()
    assert s3.objects[sha] == data


async def test_put_creates_row_with_refcount_one(db, store):
    sha = await store.put(db, b"payload")

    blob = (await db.execute(select(Blob).where(Blob.sha256 == sha))).scalar_one()
    assert blob.refcount == 1
    assert blob.size == len(b"payload")


async def test_same_content_is_stored_once(db, store, s3):
    first = await store.put(db, b"same bytes")
    second = await store.put(db, b"same bytes")

    assert first == second
    # dedup: one object in storage, two references in the row
    assert s3.put_calls == 1
    blob = (await db.execute(select(Blob).where(Blob.sha256 == first))).scalar_one()
    assert blob.refcount == 2


async def test_different_content_gets_different_keys(db, store, s3):
    a = await store.put(db, b"aaa")
    b = await store.put(db, b"bbb")

    assert a != b
    assert len(s3.objects) == 2


async def test_get_roundtrip(db, store):
    sha = await store.put(db, b"round trip")
    assert await store.get(sha) == b"round trip"


async def test_add_ref_and_release_move_the_counter(db, store):
    sha = await store.put(db, b"counted")
    await store.add_ref(db, sha)
    await store.release(db, sha)

    blob = (await db.execute(select(Blob).where(Blob.sha256 == sha))).scalar_one()
    assert blob.refcount == 1


async def test_release_never_goes_below_zero(db, store):
    sha = await store.put(db, b"floor")
    await store.release(db, sha)
    await store.release(db, sha)

    blob = (await db.execute(select(Blob).where(Blob.sha256 == sha))).scalar_one()
    assert blob.refcount == 0


async def test_release_keeps_the_object(db, store, s3):
    # deletion is the GC's job (YCA-210), release only drops a reference
    sha = await store.put(db, b"kept")
    await store.release(db, sha)
    assert sha in s3.objects


async def test_bucket_is_created_once(db, store, s3):
    await store.put(db, b"one")
    await store.put(db, b"two")
    assert s3.bucket_created
