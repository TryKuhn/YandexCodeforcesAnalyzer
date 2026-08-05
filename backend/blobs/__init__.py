"""Content-addressed storage (MinIO/S3) with refcounted dedup."""
from .store import BlobStore

__all__ = ["BlobStore"]
