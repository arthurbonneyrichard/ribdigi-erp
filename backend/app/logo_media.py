"""Company logo derivatives, HTTP caching, and the inline email logo.

The uploaded original stays in storage (print/PDF read it). Each upload also gets a
small display copy for the app chrome, and emails use a flattened PNG/JPEG small
enough to attach inline (CID). Storage keys are ``{tenant_id}/logos/{uuid}.ext`` and
are never overwritten in place, so a key hash is a safe version / ETag.
"""

from __future__ import annotations

import hashlib
import io
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import Response

from app import storage as storage_svc

logger = logging.getLogger(__name__)

DISPLAY_MAX_PX = 512
# Email header box is 240×80 CSS px; render the bitmap at 2× for sharp HiDPI clients.
EMAIL_BOX_W = 240
EMAIL_BOX_H = 80
VERSIONED_CACHE_CONTROL = "private, max-age=31536000, immutable"
REVALIDATE_CACHE_CONTROL = "private, no-cache"
_CACHE_MAX = 128
_DISPLAY_CACHE_MAX_BYTES = 512_000

_lock = threading.Lock()
_display_cache: OrderedDict[tuple[str, str], tuple[bytes, str]] = OrderedDict()
_email_cache: OrderedDict[tuple[str, str], "EmailLogo | None"] = OrderedDict()


@dataclass(frozen=True)
class EmailLogo:
    data: bytes
    subtype: str  # png | jpeg
    width: int
    height: int
    cid: str


def logo_version(tenant_id: Any, key: str | None) -> str | None:
    if not key:
        return None
    return hashlib.sha256(f"{tenant_id}:{key}".encode("utf-8")).hexdigest()[:16]


def tenant_logo_version(tenant: Any | None) -> str | None:
    if tenant is None:
        return None
    return logo_version(getattr(tenant, "id", ""), getattr(tenant, "logo_url", None))


def _derivative_keys(key: str) -> list[str]:
    path = PurePosixPath(key)
    stem = str(path.with_suffix(""))
    return [f"{stem}.display.webp", f"{stem}.display.png"]


def _cache_get(cache: OrderedDict, k: tuple[str, str]):
    with _lock:
        if k in cache:
            cache.move_to_end(k)
            return True, cache[k]
    return False, None


def _cache_put(cache: OrderedDict, k: tuple[str, str], value) -> None:
    with _lock:
        cache[k] = value
        cache.move_to_end(k)
        while len(cache) > _CACHE_MAX:
            cache.popitem(last=False)


def _evict(tenant_id: str, key: str) -> None:
    with _lock:
        _display_cache.pop((tenant_id, key), None)
        _email_cache.pop((tenant_id, key), None)


def clear_caches() -> None:
    with _lock:
        _display_cache.clear()
        _email_cache.clear()


def _open_image(data: bytes):
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(data))
    img.seek(0)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    has_alpha = img.mode in {"RGBA", "LA", "PA"} or (
        img.mode == "P" and "transparency" in img.info
    )
    return img.convert("RGBA" if has_alpha else "RGB")


def flatten_on_white(img):
    from PIL import Image

    if img.mode != "RGBA":
        return img.convert("RGB")
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.getchannel("A"))
    return bg


def build_display_bytes(data: bytes) -> tuple[bytes, str]:
    """Downscale to ≤DISPLAY_MAX_PX on the long edge; keep transparency. Returns (bytes, ext)."""
    from PIL import Image

    img = _open_image(data)
    img.thumbnail((DISPLAY_MAX_PX, DISPLAY_MAX_PX), Image.LANCZOS)
    buf = io.BytesIO()
    try:
        img.save(buf, format="WEBP", quality=86, method=4)
        return buf.getvalue(), ".webp"
    except Exception:
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), ".png"


def store_display_copy(tenant_id: str, key: str) -> str | None:
    """Write the display derivative next to the original. None when Pillow cannot read it."""
    try:
        original = storage_svc.read_object(key, tenant_id=tenant_id)
        data, ext = build_display_bytes(original.data)
    except HTTPException:
        raise
    except Exception:
        logger.warning("logo display copy skipped", exc_info=True)
        return None
    stem = str(PurePosixPath(key).with_suffix(""))
    dkey = f"{stem}.display{ext}"
    storage_svc.validate_key(dkey, tenant_id=tenant_id)
    storage_svc._put_bytes(dkey, data, storage_svc.content_type_for_key(dkey))
    if len(data) <= _DISPLAY_CACHE_MAX_BYTES:
        _cache_put(_display_cache, (str(tenant_id), key), (data, storage_svc.content_type_for_key(dkey)))
    return dkey


def delete_logo(key: str | None, *, tenant_id: str) -> None:
    """Remove the original and its derivatives; drop cached bytes."""
    if not key or "://" in key:
        return
    storage_svc.delete_key(key, tenant_id=tenant_id)
    for dkey in _derivative_keys(key):
        try:
            storage_svc.delete_key(dkey, tenant_id=tenant_id)
        except HTTPException:
            pass
    _evict(str(tenant_id), key)


def _display_bytes(tenant_id: str, key: str) -> tuple[bytes, str]:
    hit, value = _cache_get(_display_cache, (tenant_id, key))
    if hit:
        return value
    for dkey in _derivative_keys(key):
        try:
            media = storage_svc.read_object(dkey, tenant_id=tenant_id)
        except HTTPException as exc:
            if exc.status_code == 404:
                continue
            raise
        value = (media.data, media.content_type)
        if len(media.data) <= _DISPLAY_CACHE_MAX_BYTES:
            _cache_put(_display_cache, (tenant_id, key), value)
        return value
    # Logo uploaded before display copies existed: build it once, then serve.
    if store_display_copy(tenant_id, key):
        hit, value = _cache_get(_display_cache, (tenant_id, key))
        if hit:
            return value
        return _display_bytes(tenant_id, key)
    media = storage_svc.read_object(key, tenant_id=tenant_id)
    return media.data, media.content_type


def _etag_matches(request: Request | None, etag: str) -> bool:
    if request is None:
        return False
    raw = request.headers.get("if-none-match") or ""
    if not raw:
        return False
    if raw.strip() == "*":
        return True
    candidates = {part.strip().removeprefix("W/") for part in raw.split(",")}
    return etag in candidates


def cache_headers(etag: str, cache_control: str, vary: str) -> dict[str, str]:
    return {"ETag": etag, "Cache-Control": cache_control, "Vary": vary}


def tenant_logo_response(tenant: Any, *, request: Request | None, requested_version: str | None) -> Response:
    tenant_id = str(tenant.id)
    key = tenant.logo_url
    version = logo_version(tenant_id, key)
    etag = f'"{version}"'
    cache_control = (
        VERSIONED_CACHE_CONTROL if requested_version and requested_version == version else REVALIDATE_CACHE_CONTROL
    )
    headers = cache_headers(etag, cache_control, "Authorization, X-Tenant-ID")
    if _etag_matches(request, etag):
        return Response(status_code=304, headers=headers)
    data, content_type = _display_bytes(tenant_id, key)
    headers["Content-Disposition"] = f'inline; filename="logo{storage_svc.EXT_FOR_TYPE.get(content_type, "")}"'
    return Response(content=data, media_type=content_type, headers=headers)


def keyed_media_response(
    key: str,
    *,
    tenant_id: Any,
    request: Request | None,
    cache_control: str,
    vary: str,
) -> Response:
    """ETag/304 for immutable uploaded media keys (storefront logo/banner/favicon/product image)."""
    etag = f'"{logo_version(tenant_id, key)}"'
    headers = cache_headers(etag, cache_control, vary)
    if _etag_matches(request, etag):
        return Response(status_code=304, headers=headers)
    response = storage_svc.media_response(key, tenant_id=tenant_id)
    response.headers.update(headers)
    return response


def _build_email_logo(tenant_id: str, key: str) -> EmailLogo | None:
    from PIL import Image

    original = storage_svc.read_object(key, tenant_id=tenant_id)
    img = flatten_on_white(_open_image(original.data))
    img.thumbnail((EMAIL_BOX_W * 2, EMAIL_BOX_H * 2), Image.LANCZOS)
    png = io.BytesIO()
    img.save(png, format="PNG", optimize=True)
    jpg = io.BytesIO()
    img.save(jpg, format="JPEG", quality=88, optimize=True)
    data, subtype = (png.getvalue(), "png")
    if len(jpg.getvalue()) < len(data) * 0.6:
        data, subtype = (jpg.getvalue(), "jpeg")
    scale = min(EMAIL_BOX_W / img.width, EMAIL_BOX_H / img.height, 1.0)
    width = max(1, int(round(img.width * scale)))
    height = max(1, int(round(img.height * scale)))
    version = logo_version(tenant_id, key)
    return EmailLogo(
        data=data,
        subtype=subtype,
        width=width,
        height=height,
        cid=f"company-logo-{version}@ribdigi",
    )


def email_logo(tenant: Any | None) -> EmailLogo | None:
    """Small inline email logo for this tenant, cached per (tenant, logo key)."""
    if tenant is None or not getattr(tenant, "logo_url", None):
        return None
    tenant_id = str(getattr(tenant, "id", "") or "")
    key = tenant.logo_url
    if not tenant_id or "://" in key:
        return None
    hit, value = _cache_get(_email_cache, (tenant_id, key))
    if hit:
        return value
    try:
        value = _build_email_logo(tenant_id, key)
    except Exception:
        logger.warning("email logo unavailable", exc_info=True)
        return None
    _cache_put(_email_cache, (tenant_id, key), value)
    return value
