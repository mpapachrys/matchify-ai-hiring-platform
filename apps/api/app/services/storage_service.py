"""Object storage — MinIO, via the official MinIO Python client.

The API authorizes a transfer and mints a short-lived presigned URL; the browser
then talks to MinIO directly. File bytes never pass through FastAPI, so a slow
upload cannot occupy a worker for the duration of the transfer.

Two clients, one bucket: presigning must be signed against the *public* endpoint
the browser can reach, while server-side operations use the internal compose
hostname.
"""

import io
import mimetypes
import uuid
from datetime import timedelta
from functools import lru_cache
from urllib.parse import urlsplit

from minio import Minio

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.enums import DocumentType

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png",
    "image/jpeg",
    "image/webp",
}


@lru_cache
def _client(endpoint: str) -> Minio:
    """MinIO wants a bare host:port plus a TLS flag, not a URL.

    `region` is passed explicitly and deliberately: without it the client makes a
    live bucket-location request before signing. The public client is configured
    with the hostname the *browser* resolves, which the API container cannot
    reach — so that lookup would fail every presign. Supplying the region skips
    it and makes presigning a pure local computation.
    """
    parts = urlsplit(endpoint)
    host = parts.netloc or parts.path
    return Minio(
        host,
        access_key=settings.storage_access_key,
        secret_key=settings.storage_secret_key,
        secure=parts.scheme == "https",
        region=settings.storage_region,
    )


def _public_client() -> Minio:
    return _client(settings.storage_endpoint_public)


def internal_client() -> Minio:
    """Server-side operations (reads, deletes) over the compose network."""
    return _client(settings.storage_endpoint_internal)


def _ttl() -> timedelta:
    return timedelta(seconds=settings.presign_ttl_seconds)


def build_object_key(owner_id: str, doc_type: DocumentType, filename: str) -> str:
    """Random prefix keeps keys unguessable and avoids collisions on re-upload."""
    suffix = "".join(c for c in filename[-40:] if c.isalnum() or c in "._-") or "file"
    return f"{owner_id}/{doc_type.value}/{uuid.uuid4().hex}-{suffix}"


def validate_upload(content_type: str, size_bytes: int) -> None:
    if size_bytes > settings.max_upload_bytes:
        raise ValidationError(f"File exceeds the {settings.max_upload_mb} MB limit")
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(f"Unsupported file type: {content_type}")


def presign_upload(object_key: str) -> str:
    return _public_client().presigned_put_object(
        settings.storage_bucket, object_key, expires=_ttl()
    )


def presign_download(
    object_key: str, filename: str | None = None, *, attachment: bool = False
) -> str:
    """`attachment=True` makes the browser save the file instead of previewing it.

    Reviewing an applicant's CV wants a preview tab; a "Download" button should
    put the file on disk. Same object, different content-disposition.
    """
    headers: dict[str, str] | None = None
    if filename:
        guessed = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        disposition = "attachment" if attachment else "inline"
        headers = {
            "response-content-disposition": f'{disposition}; filename="{filename}"',
            "response-content-type": guessed,
        }
    return _public_client().presigned_get_object(
        settings.storage_bucket,
        object_key,
        expires=_ttl(),
        response_headers=headers,
    )


def delete_object(object_key: str) -> None:
    internal_client().remove_object(settings.storage_bucket, object_key)


def put_object(object_key: str, data: bytes, content_type: str) -> None:
    """Server-side upload — used for artifacts the API generates itself
    (a rendered resume PDF), as opposed to browser uploads which are presigned."""
    internal_client().put_object(
        settings.storage_bucket,
        object_key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
