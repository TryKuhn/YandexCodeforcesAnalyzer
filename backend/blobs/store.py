"""Content-addressed blob store: dedup by sha256, refcount decides what may be deleted."""
import hashlib
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import aioboto3
from botocore.exceptions import ClientError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.blobs.blob import Blob
from settings import settings

ClientFactory = Callable[[], AbstractAsyncContextManager[Any]]


def _default_client_factory() -> AbstractAsyncContextManager[Any]:
    session = aioboto3.Session()
    return session.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )


def _is_missing(error: ClientError) -> bool:
    code = error.response.get("Error", {}).get("Code", "")
    return code in ("404", "NoSuchKey", "NoSuchBucket")


class BlobStore:
    def __init__(
        self,
        *,
        bucket: str | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._bucket = bucket or settings.S3_BUCKET
        self._client = client_factory or _default_client_factory
        self._bucket_ready = False

    async def _ensure_bucket(self, s3: Any) -> None:
        if self._bucket_ready:
            return
        try:
            await s3.head_bucket(Bucket=self._bucket)
        except ClientError as error:
            if not _is_missing(error):
                raise
            await s3.create_bucket(Bucket=self._bucket)
        self._bucket_ready = True

    async def put(self, db: AsyncSession, data: bytes) -> str:
        """Store bytes, return their sha256; the same content is stored once."""
        sha = hashlib.sha256(data).hexdigest()
        # upload before the row: an orphan object is harmless, a dangling row is not
        async with self._client() as s3:
            await self._ensure_bucket(s3)
            try:
                await s3.head_object(Bucket=self._bucket, Key=sha)
            except ClientError as error:
                if not _is_missing(error):
                    raise
                await s3.put_object(Bucket=self._bucket, Key=sha, Body=data)

        bumped = await db.execute(
            update(Blob)
            .where(Blob.sha256 == sha)
            .values(refcount=Blob.refcount + 1)
            .returning(Blob.sha256)
        )
        if bumped.first() is None:
            db.add(Blob(sha256=sha, size=len(data)))
            try:
                await db.commit()
            except IntegrityError:
                # somebody inserted the same hash first: count us in instead
                await db.rollback()
                await db.execute(
                    update(Blob)
                    .where(Blob.sha256 == sha)
                    .values(refcount=Blob.refcount + 1)
                )
                await db.commit()
        else:
            await db.commit()
        return sha

    async def get(self, sha: str) -> bytes:
        async with self._client() as s3:
            response = await s3.get_object(Bucket=self._bucket, Key=sha)
            return await response["Body"].read()

    async def add_ref(self, db: AsyncSession, sha: str) -> None:
        await db.execute(
            update(Blob).where(Blob.sha256 == sha).values(refcount=Blob.refcount + 1)
        )
        await db.commit()

    async def release(self, db: AsyncSession, sha: str) -> None:
        """Drop one reference; actual deletion is the GC's job (YCA-210)."""
        await db.execute(
            update(Blob)
            .where(Blob.sha256 == sha, Blob.refcount > 0)
            .values(refcount=Blob.refcount - 1)
        )
        await db.commit()
