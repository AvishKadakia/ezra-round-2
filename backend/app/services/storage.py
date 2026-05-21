from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import boto3
import certifi
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError, NoCredentialsError

from app.core.config import get_settings

settings = get_settings()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

class StorageError(RuntimeError):
    """Raised when the S3-compatible blob store cannot complete an operation."""


def _s3_verify_value() -> bool | str:
    """Return the SSL verification setting passed directly to boto3.

    Passing this explicitly prevents a broken local AWS_CA_BUNDLE / REQUESTS_CA_BUNDLE
    environment variable from making boto3 look for a non-existent certificate file.
    """

    if not settings.s3_ssl_verify:
        return False

    if settings.s3_ca_bundle.strip():
        ca_path = Path(settings.s3_ca_bundle).expanduser()
        if not ca_path.exists():
            raise StorageError(
                f"Blob storage SSL setup failed: S3_CA_BUNDLE points to a file that does not exist: {ca_path}"
            )
        return str(ca_path)

    return certifi.where()


def _safe_storage_message(operation: str, error: BaseException) -> str:
    """Return a user-actionable message without leaking secret values."""

    if isinstance(error, NoCredentialsError):
        return f"Blob storage {operation} failed: missing access key or secret key. Check backend/.env storage credentials."
    if isinstance(error, EndpointConnectionError):
        return f"Blob storage {operation} failed: could not reach S3 endpoint. Check S3_ENDPOINT_URL."
    if isinstance(error, ClientError):
        err = error.response.get("Error", {})
        code = err.get("Code", "ClientError")
        message = err.get("Message", "Storage service rejected the request")
        return f"Blob storage {operation} failed: {code} - {message}. Check bucket name, endpoint, and key permissions."

    error_text = str(error)
    if type(error).__name__ == "SSLError" or "SSL validation failed" in error_text:
        if "No such file or directory" in error_text:
            return (
                f"Blob storage {operation} failed: Python/boto3 could not find a usable CA certificate bundle. "
                "The app now uses certifi by default; run `make install` again, restart the backend, and make sure "
                "S3_CA_BUNDLE is blank unless it points to a real .pem file."
            )
        return (
            f"Blob storage {operation} failed: SSL certificate validation failed for the bucket endpoint. "
            "Check S3_ENDPOINT_URL, local certificate/proxy settings, or set S3_CA_BUNDLE to a valid .pem file."
        )

    return f"Blob storage {operation} failed: {type(error).__name__}: {error_text[:300]}"


def s3_client():
    # Short timeouts prevent a bad endpoint/bucket configuration from leaving the
    # Publish modal stuck in “Uploading...” for a long time.
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
        verify=_s3_verify_value(),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=settings.s3_connect_timeout_seconds,
            read_timeout=settings.s3_read_timeout_seconds,
            retries={"max_attempts": settings.s3_max_attempts, "mode": "standard"},
        ),
    )


def upload_fileobj(fileobj, object_key: str, content_type: str | None = None) -> None:
    """
    Upload one already-validated file to blob storage.

    Since the app caps files at 10 MB, a single put_object call is safer than
    managed multipart upload for S3-compatible providers.
    """
    try:
        fileobj.seek(0)
        body = fileobj.read()

        if len(body) > settings:
            raise StorageError("File is larger than the 10 MB upload limit.")

        get_storage_client().put_object(
            Bucket=settings.bucket_name,
            Key=object_key,
            Body=body,
            ContentType=content_type or "application/octet-stream",
        )

    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        message = exc.response.get("Error", {}).get("Message", str(exc))
        raise StorageError(
            f"Blob storage upload failed: {code} - {message}. "
            "Check bucket name, endpoint, and write permissions."
        ) from exc

    except BotoCoreError as exc:
        raise StorageError(f"Blob storage upload failed: {exc}") from exc


def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    try:
        s3_client().put_object(Bucket=settings.s3_bucket_name, Key=key, Body=data, ContentType=content_type)
    except StorageError:
        raise
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(_safe_storage_message("upload", exc)) from exc


def download_bytes(key: str) -> bytes:
    try:
        obj = s3_client().get_object(Bucket=settings.s3_bucket_name, Key=key)
        return obj["Body"].read()
    except StorageError:
        raise
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(_safe_storage_message("download", exc)) from exc


def download_to_path(key: str, destination: Path) -> None:
    """Stream an object to disk using plain get_object.

    Do not use boto3's managed download_fileobj() here. Some S3-compatible
    providers allow GetObject but reject HeadObject or transfer-manager helper
    calls with 403. The preview route already works via get_object(), so the
    worker should use the exact same lower-level download path.
    """

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        obj = s3_client().get_object(Bucket=settings.s3_bucket_name, Key=key)
        with destination.open("wb") as buffer:
            for chunk in iter_streaming_body(obj["Body"]):
                buffer.write(chunk)
    except StorageError:
        raise
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(_safe_storage_message("download", exc)) from exc


def get_object_response(key: str, byte_range: str | None = None):
    """Return a boto3 get_object response for FastAPI streaming.

    byte_range should be in S3 format, for example: bytes=0-1023.
    This keeps previews/PDFs efficient and lets browsers request partial content.
    """
    try:
        kwargs = {"Bucket": settings.s3_bucket_name, "Key": key}
        if byte_range:
            kwargs["Range"] = byte_range
        return s3_client().get_object(**kwargs)
    except StorageError:
        raise
    except (BotoCoreError, ClientError) as exc:
        raise StorageError(_safe_storage_message("download", exc)) from exc


def iter_streaming_body(body, chunk_size: int = 1024 * 256):
    try:
        while True:
            chunk = body.read(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        close = getattr(body, "close", None)
        if callable(close):
            close()


def make_api_file_url(artifact_id: str) -> str:
    base = settings.public_api_base_url.rstrip("/")
    return f"{base}/files/{artifact_id}" if base else f"/files/{artifact_id}"
