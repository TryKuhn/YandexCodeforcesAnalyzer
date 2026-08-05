"""Fixtures for blob-store tests: in-memory S3 plus the shared sqlite session."""
from contextlib import asynccontextmanager

import pytest
from botocore.exceptions import ClientError

from blobs import BlobStore


def _missing(operation: str) -> ClientError:
    return ClientError({"Error": {"Code": "404"}}, operation)


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def read(self) -> bytes:
        return self._data


class FakeS3:
    """Just enough of the S3 client surface for BlobStore."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.bucket_created = False
        self.put_calls = 0

    async def head_bucket(self, Bucket):
        if not self.bucket_created:
            raise _missing("HeadBucket")

    async def create_bucket(self, Bucket):
        self.bucket_created = True

    async def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise _missing("HeadObject")

    async def put_object(self, Bucket, Key, Body):
        self.put_calls += 1
        self.objects[Key] = Body

    async def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise _missing("GetObject")
        return {"Body": _Body(self.objects[Key])}


@pytest.fixture
def s3() -> FakeS3:
    return FakeS3()


@pytest.fixture
def store(s3) -> BlobStore:
    @asynccontextmanager
    async def factory():
        yield s3

    return BlobStore(bucket="test-bucket", client_factory=factory)
