"""Tenant-scoped media storage: local filesystem or S3/MinIO-compatible object store."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response

from app.config import settings

SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

LOGO_CONTENT_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
)
ATTACHMENT_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
        "image/gif",
    }
)

EXT_FOR_TYPE = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "application/pdf": ".pdf",
}

CONTENT_TYPE_FOR_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
}


@dataclass
class StoredObject:
    key: str
    content_type: str
    size: int
    original_filename: str | None
    backend: str = "local"


@dataclass
class MediaObject:
    key: str
    data: bytes
    content_type: str
    filename: str
    backend: str


def storage_backend() -> str:
    backend = (settings.STORAGE_BACKEND or "local").strip().lower()
    if backend in {"s3", "minio", "object"}:
        return "s3"
    return "local"


def media_root() -> Path:
    root = Path(settings.MEDIA_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_filename(name: str | None) -> str:
    raw = (name or "file").strip().replace("\\", "/").split("/")[-1]
    cleaned = SAFE_NAME.sub("_", raw).strip("._") or "file"
    return cleaned[:120]


def _normalize_content_type(content_type: str | None) -> str:
    ct = (content_type or "application/octet-stream").split(";")[0].strip().lower()
    if ct == "image/jpg":
        return "image/jpeg"
    return ct


def content_type_for_key(key: str) -> str:
    suffix = Path(key).suffix.lower()
    return CONTENT_TYPE_FOR_EXT.get(suffix, "application/octet-stream")


def build_key(tenant_id: str, category: str, content_type: str, original_filename: str | None) -> str:
    category = SAFE_NAME.sub("", category) or "files"
    ext = EXT_FOR_TYPE.get(content_type)
    if not ext and original_filename and "." in original_filename:
        ext = "." + original_filename.rsplit(".", 1)[-1].lower()[:8]
    if not ext:
        ext = ".bin"
    return f"{tenant_id}/{category}/{uuid.uuid4().hex}{ext}"


def validate_key(key: str, *, tenant_id: str | None = None) -> str:
    if not key or "://" in key or ".." in key or key.startswith(("/", "\\")):
        raise HTTPException(status_code=400, detail="Invalid media key")
    parts = Path(key).parts
    if not parts or any(p in {"", ".", ".."} for p in parts):
        raise HTTPException(status_code=400, detail="Invalid media key")
    if tenant_id and parts[0] != tenant_id:
        raise HTTPException(status_code=403, detail="Media key tenant mismatch")
    return key.replace("\\", "/")


def resolve_key(key: str, *, tenant_id: str | None = None) -> Path:
    """Resolve a local filesystem path for a media key (local backend only)."""
    key = validate_key(key, tenant_id=tenant_id)
    root = media_root().resolve()
    path = (root / key).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid media path") from exc
    return path


@lru_cache(maxsize=1)
def _s3_client():
    try:
        import boto3
        from botocore.client import Config
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="S3 storage requires boto3 (install backend requirements)",
        ) from exc

    endpoint = (settings.S3_ENDPOINT or settings.S3_ENDPOINT_URL or "").strip() or None
    access = (settings.S3_ACCESS_KEY or "").strip()
    secret = (settings.S3_SECRET_KEY or "").strip()
    region = (settings.S3_REGION or "us-east-1").strip()
    if not access or not secret:
        raise HTTPException(
            status_code=503,
            detail="S3_ACCESS_KEY and S3_SECRET_KEY are required when STORAGE_BACKEND=s3",
        )
    if not (settings.S3_BUCKET or "").strip():
        raise HTTPException(status_code=503, detail="S3_BUCKET is required when STORAGE_BACKEND=s3")

    addressing = "path" if settings.S3_FORCE_PATH_STYLE else "auto"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=region,
        config=Config(s3={"addressing_style": addressing}, signature_version="s3v4"),
    )


def _s3_bucket() -> str:
    return (settings.S3_BUCKET or "").strip()


def ensure_bucket() -> None:
    if storage_backend() != "s3":
        return
    client = _s3_client()
    bucket = _s3_bucket()
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        try:
            kwargs: dict = {"Bucket": bucket}
            region = (settings.S3_REGION or "us-east-1").strip()
            # MinIO / path-style often accepts CreateBucket without LocationConstraint
            if region and region != "us-east-1" and not (settings.S3_ENDPOINT or "").strip():
                kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
            client.create_bucket(**kwargs)
        except Exception as exc:
            # Race: bucket created by another worker
            try:
                client.head_bucket(Bucket=bucket)
            except Exception:
                raise HTTPException(
                    status_code=503,
                    detail=f"Unable to access or create S3 bucket '{bucket}': {exc}",
                ) from exc


def _put_bytes(key: str, data: bytes, content_type: str) -> None:
    if storage_backend() == "s3":
        ensure_bucket()
        _s3_client().put_object(
            Bucket=_s3_bucket(),
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return
    path = resolve_key(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _get_bytes(key: str) -> bytes:
    if storage_backend() == "s3":
        try:
            obj = _s3_client().get_object(Bucket=_s3_bucket(), Key=key)
            return obj["Body"].read()
        except Exception as exc:
            raise HTTPException(status_code=404, detail="Media file not found") from exc
    path = resolve_key(key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")
    return path.read_bytes()


def _delete_bytes(key: str) -> bool:
    if storage_backend() == "s3":
        try:
            _s3_client().delete_object(Bucket=_s3_bucket(), Key=key)
            return True
        except Exception:
            return False
    path = resolve_key(key)
    if path.is_file():
        path.unlink()
        return True
    return False


async def save_upload(
    *,
    tenant_id: str,
    category: str,
    upload: UploadFile,
    allowed_types: frozenset[str],
    max_bytes: int,
) -> StoredObject:
    content_type = _normalize_content_type(upload.content_type)
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {content_type}. Allowed: {sorted(allowed_types)}",
        )
    data = await upload.read()
    size = len(data)
    if size <= 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if size > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size of {max_bytes} bytes",
        )
    original = sanitize_filename(upload.filename)
    key = build_key(tenant_id, category, content_type, original)
    validate_key(key, tenant_id=tenant_id)
    _put_bytes(key, data, content_type)
    return StoredObject(
        key=key,
        content_type=content_type,
        size=size,
        original_filename=original,
        backend=storage_backend(),
    )


def delete_key(key: str | None, *, tenant_id: str | None = None) -> bool:
    if not key:
        return False
    # External http(s) URLs are not managed by this store
    if "://" in key:
        return False
    key = validate_key(key, tenant_id=tenant_id)
    return _delete_bytes(key)


def read_object(key: str, *, tenant_id: str | None = None) -> MediaObject:
    key = validate_key(key, tenant_id=tenant_id)
    data = _get_bytes(key)
    filename = Path(key).name
    return MediaObject(
        key=key,
        data=data,
        content_type=content_type_for_key(key),
        filename=filename,
        backend=storage_backend(),
    )


def open_key(key: str, *, tenant_id: str | None = None) -> tuple[Path, str]:
    """Local-backend helper: return filesystem path. Prefer read_object / media_response."""
    if storage_backend() != "local":
        raise HTTPException(
            status_code=400,
            detail="open_key is only available for STORAGE_BACKEND=local; use read_object",
        )
    path = resolve_key(key, tenant_id=tenant_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")
    return path, content_type_for_key(key)


def media_response(
    key: str,
    *,
    tenant_id: str | None = None,
    as_attachment: bool = False,
) -> Response:
    media = read_object(key, tenant_id=tenant_id)
    disposition = "attachment" if as_attachment else "inline"
    return Response(
        content=media.data,
        media_type=media.content_type,
        headers={"Content-Disposition": f'{disposition}; filename="{media.filename}"'},
    )


def storage_status() -> dict:
    backend = storage_backend()
    info: dict = {
        "backend": backend,
        "media_dir": settings.MEDIA_DIR if backend == "local" else None,
        "bucket": _s3_bucket() if backend == "s3" else None,
        "endpoint": (settings.S3_ENDPOINT or settings.S3_ENDPOINT_URL or None)
        if backend == "s3"
        else None,
        "region": settings.S3_REGION if backend == "s3" else None,
    }
    return info


def reset_s3_client_cache() -> None:
    """Test helper: clear cached boto3 client after settings monkeypatch."""
    clear = getattr(_s3_client, "cache_clear", None)
    if callable(clear):
        clear()
