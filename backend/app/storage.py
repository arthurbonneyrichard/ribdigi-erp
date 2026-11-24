"""Tenant-scoped media storage: local filesystem or S3/MinIO-compatible object store."""

from __future__ import annotations

import asyncio
import io
import logging
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response

from app.config import settings

logger = logging.getLogger(__name__)

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


def _sniff_media_type(data: bytes) -> str | None:
    if not data:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _reject_untrusted_upload(*, filename: str | None, claimed: str, data: bytes) -> str:
    name = (filename or "").lower()
    if claimed in {"image/svg+xml", "text/xml", "application/xml"} or name.endswith(".svg"):
        raise HTTPException(
            status_code=400,
            detail="That file type is not allowed. Use PNG, JPEG, WebP, or GIF.",
        )
    head = data[:256].lstrip().lower()
    if head.startswith(b"<svg") or head.startswith(b"<?xml") or b"<svg" in head:
        raise HTTPException(
            status_code=400,
            detail="That file type is not allowed. Use PNG, JPEG, WebP, or GIF.",
        )
    sniffed = _sniff_media_type(data)
    if claimed.startswith("image/") or claimed == "application/pdf":
        if sniffed is None:
            raise HTTPException(
                status_code=400,
                detail="That file type is not allowed. Use PNG, JPEG, WebP, or GIF.",
            )
        if sniffed != claimed:
            raise HTTPException(
                status_code=400,
                detail="That file type is not allowed. Use PNG, JPEG, WebP, or GIF.",
            )
        return sniffed
    return claimed


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
            detail="Object storage is not available.",
        ) from exc

    endpoint = (settings.S3_ENDPOINT or settings.S3_ENDPOINT_URL or "").strip() or None
    access = (settings.S3_ACCESS_KEY or "").strip()
    secret = (settings.S3_SECRET_KEY or "").strip()
    region = (settings.S3_REGION or "us-east-1").strip()
    if not access or not secret:
        raise HTTPException(
            status_code=503,
            detail="Object storage is not configured.",
        )
    if not (settings.S3_BUCKET or "").strip():
        raise HTTPException(status_code=503, detail="Object storage is not configured.")

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


# Longest side, in pixels, kept for each kind of upload. Phone photos are 4000 px and several MB;
# a till tile, menu card or catalogue row never needs more than this, so uploads are shrunk once
# here and every screen opens faster. The company logo is not listed: its original is kept for
# printing and PDFs. Receipts and documents keep more detail so text stays readable.
IMAGE_MAX_SIDE = {
    "product_images": 1280,
    "brand_logos": 800,
    "banners": 1600,
    "favicons": 256,
    "ecommerce_banner": 1600,
    "purchase_invoices": 2400,
    "expenses": 2400,
    "journals": 2400,
}


def optimize_image(data: bytes, content_type: str, max_side: int) -> tuple[bytes, str]:
    """Shrink and recompress a picture, keeping its format. Any trouble returns the original bytes."""
    if content_type not in {"image/png", "image/jpeg", "image/jpg", "image/webp"}:
        return data, content_type  # GIFs may be animated; leave them alone
    try:
        from PIL import Image, ImageOps

        with Image.open(io.BytesIO(data)) as img:
            if getattr(img, "n_frames", 1) > 1:
                return data, content_type
            img.load()
            fixed = ImageOps.exif_transpose(img)  # also drops the camera's GPS/EXIF block
            resized = max(fixed.size) > max_side
            if resized:
                fixed.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            if content_type == "image/png":
                fixed.save(out, "PNG", optimize=True)
            elif content_type == "image/webp":
                fixed.save(out, "WEBP", quality=82, method=4)
            else:
                if fixed.mode not in ("RGB", "L"):
                    fixed = fixed.convert("RGB")
                fixed.save(out, "JPEG", quality=82, optimize=True, progressive=True)
        result = out.getvalue()
        if resized or len(result) < len(data):
            return result, content_type
    except Exception:  # noqa: BLE001 - a picture we cannot recompress is still stored as sent
        logger.warning("image optimisation skipped", exc_info=True)
    return data, content_type


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
            detail="That file type is not allowed. Use PNG, JPEG, WebP, or GIF.",
        )
    data = await upload.read()
    size = len(data)
    if size <= 0:
        raise HTTPException(status_code=400, detail="The file is empty. Choose another image.")
    content_type = _reject_untrusted_upload(
        filename=upload.filename, claimed=content_type, data=data
    )
    if size > max_bytes:
        max_mb = max(1, int(max_bytes / 1_000_000))
        raise HTTPException(
            status_code=400,
            detail=f"That file is too large. Maximum size is {max_mb} MB.",
        )
    max_side = IMAGE_MAX_SIDE.get(category)
    if max_side:
        data, content_type = await asyncio.to_thread(optimize_image, data, content_type, max_side)
        size = len(data)
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
            detail="This media file cannot be opened that way.",
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
    headers = {"Content-Disposition": f'{disposition}; filename="{media.filename}"'}
    if not as_attachment and media.content_type.startswith("image/"):
        # Every upload gets a new random key and is never overwritten, so the browser may keep a
        # picture for good instead of downloading it again each time a screen opens.
        headers["Cache-Control"] = "private, max-age=31536000, immutable"
    return Response(content=media.data, media_type=media.content_type, headers=headers)


def delete_tenant_media(tenant_id: str) -> None:
    """Remove uploaded files stored under this tenant id. Other tenants stay."""
    import shutil

    tid = (tenant_id or "").strip()
    if not tid or any(part in tid for part in ("/", "\\", "..")):
        raise ValueError("invalid tenant id")
    if storage_backend() == "s3":
        ensure_bucket()
        client = _s3_client()
        bucket = _s3_bucket()
        token = None
        while True:
            kwargs = {"Bucket": bucket, "Prefix": f"{tid}/"}
            if token:
                kwargs["ContinuationToken"] = token
            page = client.list_objects_v2(**kwargs)
            keys = [{"Key": obj["Key"]} for obj in page.get("Contents") or []]
            if keys:
                client.delete_objects(Bucket=bucket, Delete={"Objects": keys})
            if not page.get("IsTruncated"):
                return
            token = page.get("NextContinuationToken")
    root = media_root().resolve()
    path = (root / tid).resolve()
    path.relative_to(root)
    if path.is_dir():
        shutil.rmtree(path)


def iter_keys(prefix: str = ""):
    """Every stored object key, optionally under a prefix (local disk or S3)."""
    if storage_backend() == "s3":
        ensure_bucket()
        client = _s3_client()
        token = None
        while True:
            kwargs = {"Bucket": _s3_bucket(), "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            page = client.list_objects_v2(**kwargs)
            for obj in page.get("Contents") or []:
                yield obj["Key"]
            if not page.get("IsTruncated"):
                return
            token = page.get("NextContinuationToken")
    root = media_root().resolve()
    base = root / prefix if prefix else root
    if base.is_dir():
        for path in base.rglob("*"):
            if path.is_file():
                yield path.relative_to(root).as_posix()


def optimize_existing(*, dry_run: bool = True) -> dict:
    """Shrink pictures uploaded before uploads were optimised. Same keys, smaller files."""
    report = {"checked": 0, "shrunk": 0, "bytes_before": 0, "bytes_after": 0}
    for key in iter_keys():
        parts = key.split("/")
        max_side = IMAGE_MAX_SIDE.get(parts[1]) if len(parts) >= 3 else None
        if not max_side:
            continue
        content_type = content_type_for_key(key)
        if not content_type.startswith("image/"):
            continue
        data = _get_bytes(key)
        report["checked"] += 1
        smaller, _ = optimize_image(data, content_type, max_side)
        if len(smaller) < len(data):
            report["shrunk"] += 1
            report["bytes_before"] += len(data)
            report["bytes_after"] += len(smaller)
            if not dry_run:
                _put_bytes(key, smaller, content_type)
    return report


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
