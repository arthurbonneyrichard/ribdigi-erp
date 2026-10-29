"""Built-in tenant storefront: domains, catalog, cart, reservations, orders."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Any, Callable, Awaitable
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app.packages import canonicalize_industry, module_allowed

TXT_PREFIX = "ribdigi-site="
CART_HOURS = 24
DEFAULT_RESERVE_MINUTES = 30
IMPLEMENTED_CONNECTORS = frozenset({"woocommerce"})
UNIMPLEMENTED_CONNECTORS = frozenset({"shopify", "squarespace", "magento", "custom"})
RETAIL_INDUSTRIES = frozenset({"retail", "pharmacy"})
OPEN_ORDER_STATUSES = frozenset({"awaiting_payment"})
PAID_ORDER_STATUSES = frozenset({"paid", "packed", "dispatched", "delivered", "fulfilled", "returned"})
FULFILLMENT_STEPS = ("paid", "packed", "dispatched", "delivered")

DnsLookup = Callable[[str], Awaitable[list[str]] | list[str]]
_dns_lookup: DnsLookup | None = None


def set_dns_lookup(fn: DnsLookup | None) -> None:
    """Tests inject a TXT resolver. Live DNS is optional and may stay BLOCKED."""
    global _dns_lookup
    _dns_lookup = fn


def new_secret_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "testserver", "host.docker.internal"})
_RESERVED_HOSTS = frozenset(
    {
        "ribdigi.com",
        "www.ribdigi.com",
        "ribdigihouse.com",
        "www.ribdigihouse.com",
        "erp.ribdigihouse.com",
    }
)
_RESERVED_SUFFIXES = (".ribdigi.com", ".ribdigihouse.com")


def hostname_from_website(value: str | None) -> str:
    """Accept a hostname or an http(s) website URL and return the public host."""
    raw = (value or "").strip()
    if "://" in raw:
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise HTTPException(status_code=400, detail="Use a public hostname or https website you control")
        host = parsed.hostname.lower()
        if parsed.scheme == "http" and host not in _LOCAL_HOSTS:
            raise HTTPException(status_code=400, detail="Remote websites must use https")
        raw = host
    return normalize_hostname(raw)


def normalize_hostname(value: str | None) -> str:
    host = (value or "").strip().lower().rstrip(".")
    if "://" in host:
        return hostname_from_website(host)
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if ":" in host and host.count(":") == 1:
        name, port = host.rsplit(":", 1)
        if port.isdigit():
            host = name
    if host.startswith("www."):
        host = host[4:]
    return host


def assert_public_hostname(host: str) -> str:
    if not host or host in _LOCAL_HOSTS:
        raise HTTPException(status_code=400, detail="Use a public hostname you control")
    if host in _RESERVED_HOSTS or host.endswith(_RESERVED_SUFFIXES):
        raise HTTPException(status_code=400, detail="There is no public Ribdigi subdomain. Use a hostname you control.")
    return host


def host_from_request(
    *,
    host: str | None,
    forwarded_host: str | None,
    peer_ip: str | None = None,
) -> str:
    """Prefer X-Forwarded-Host when unset (current deploy). Opt into Host-only."""
    from app.config import settings

    use_forwarded = bool(settings.TRUST_X_FORWARDED_HOST) and bool((forwarded_host or "").strip())
    trusted = settings.trusted_proxy_ips
    if use_forwarded and trusted and (peer_ip or "") not in trusted:
        use_forwarded = False
    raw = ((forwarded_host if use_forwarded else host) or host or "").split(",")[0].strip()
    return normalize_hostname(raw)


def assert_ecommerce_entitled(tenant: m.Tenant) -> None:
    industry = canonicalize_industry(getattr(tenant, "industry", None))
    if industry not in RETAIL_INDUSTRIES:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "INDUSTRY_MODULE_DISABLED",
                "message": "Online store is available for retail companies only.",
                "module": "ecommerce",
                "industry": industry,
            },
        )
    if not module_allowed(tenant, "ecommerce"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PACKAGE_FEATURE_DISABLED",
                "message": "Online store is not included in this company's package.",
                "module": "ecommerce",
                "package_code": getattr(tenant, "package_code", None),
            },
        )


async def get_tenant(db: AsyncSession, tenant_id: str) -> m.Tenant:
    tenant = await db.get(m.Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return tenant


async def require_storefront(db: AsyncSession, tenant_id: str) -> m.EcommerceStorefront:
    row = (
        await db.execute(
            select(m.EcommerceStorefront).where(m.EcommerceStorefront.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if row is None:
        row = m.EcommerceStorefront(
            tenant_id=tenant_id,
            preview_token=new_secret_token(24),
            reservation_minutes=DEFAULT_RESERVE_MINUTES,
        )
        db.add(row)
        await db.flush()
    return row


def serialize_storefront(row: m.EcommerceStorefront, tenant: m.Tenant) -> dict[str, Any]:
    return {
        "id": row.id,
        "enabled": bool(row.is_enabled),
        "company_name": tenant.company_name,
        "company_website": tenant.website,
        "currency": tenant.currency or "GHS",
        "tagline": row.tagline,
        "announcement": row.announcement,
        "support_email": row.support_email,
        "support_phone": row.support_phone,
        "fulfillment_warehouse_id": row.fulfillment_warehouse_id,
        "fulfillment_store_id": row.fulfillment_store_id,
        "allow_delivery": bool(row.allow_delivery),
        "allow_pickup": bool(row.allow_pickup),
        "pickup_address": row.pickup_address,
        "delivery_notes": row.delivery_notes,
        "policy_shipping": row.policy_shipping,
        "policy_returns": row.policy_returns,
        "policy_privacy": row.policy_privacy,
        "reservation_minutes": int(row.reservation_minutes or DEFAULT_RESERVE_MINUTES),
        "preview_token": row.preview_token,
        "has_logo": bool(row.logo_url),
        "has_banner": bool(row.banner_url),
        "has_favicon": bool(row.favicon_url),
    }


STOREFRONT_MEDIA_FIELDS = {
    "logo": "logo_url",
    "banner": "banner_url",
    "favicon": "favicon_url",
}


def public_product_image_path(product_id: str) -> str:
    return f"/storefront/products/{product_id}/image"


def storefront_media_attr(kind: str) -> str:
    key = (kind or "").strip().lower()
    if key not in STOREFRONT_MEDIA_FIELDS:
        raise HTTPException(status_code=404, detail="Storefront media kind not found")
    return STOREFRONT_MEDIA_FIELDS[key]


async def set_storefront_media(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    kind: str,
    storage_key: str,
) -> m.EcommerceStorefront:
    from app import storage as storage_svc

    assert_ecommerce_entitled(tenant)
    row = await require_storefront(db, tenant.id)
    attr = storefront_media_attr(kind)
    previous = getattr(row, attr)
    if previous and previous != storage_key:
        storage_svc.delete_key(previous, tenant_id=tenant.id)
    setattr(row, attr, storage_key)
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def clear_storefront_media(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    kind: str,
) -> m.EcommerceStorefront:
    from app import storage as storage_svc

    assert_ecommerce_entitled(tenant)
    row = await require_storefront(db, tenant.id)
    attr = storefront_media_attr(kind)
    previous = getattr(row, attr)
    if not previous:
        raise HTTPException(status_code=404, detail=f"No storefront {kind} uploaded")
    storage_svc.delete_key(previous, tenant_id=tenant.id)
    setattr(row, attr, None)
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def update_storefront(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    payload: dict[str, Any],
) -> m.EcommerceStorefront:
    assert_ecommerce_entitled(tenant)
    row = await require_storefront(db, tenant.id)
    if "is_enabled" in payload and payload["is_enabled"] is not None:
        row.is_enabled = bool(payload["is_enabled"])
    for field, label, maxlen in (
        ("tagline", "Storefront tagline", 200),
        ("announcement", "Storefront announcement", 500),
        ("pickup_address", "Pickup address", 500),
        ("delivery_notes", "Delivery notes", 500),
        ("policy_shipping", "Shipping policy", 4000),
        ("policy_returns", "Returns policy", 4000),
        ("policy_privacy", "Privacy policy", 4000),
    ):
        if field in payload:
            setattr(
                row,
                field,
                optional_honest_narrative(payload.get(field), label=label, max_length=maxlen),
            )
    if "support_email" in payload:
        email = (payload.get("support_email") or "").strip() or None
        row.support_email = email
    if "support_phone" in payload:
        row.support_phone = (payload.get("support_phone") or "").strip() or None
    if "fulfillment_warehouse_id" in payload:
        wid = payload.get("fulfillment_warehouse_id")
        if wid:
            wh = await db.get(m.Warehouse, str(wid))
            if wh is None or wh.tenant_id != tenant.id:
                raise HTTPException(status_code=404, detail="Warehouse not found")
            row.fulfillment_warehouse_id = wh.id
        else:
            row.fulfillment_warehouse_id = None
    if "fulfillment_store_id" in payload:
        sid = payload.get("fulfillment_store_id")
        if sid:
            store = await db.get(m.Store, str(sid))
            if store is None or store.tenant_id != tenant.id:
                raise HTTPException(status_code=404, detail="Store not found")
            row.fulfillment_store_id = store.id
        else:
            row.fulfillment_store_id = None
    if payload.get("allow_delivery") is not None:
        row.allow_delivery = bool(payload["allow_delivery"])
    if payload.get("allow_pickup") is not None:
        row.allow_pickup = bool(payload["allow_pickup"])
    minutes = payload.get("reservation_minutes")
    if minutes is not None:
        mins = int(minutes)
        if mins < 5 or mins > 24 * 60:
            raise HTTPException(status_code=400, detail="Reservation minutes must be between 5 and 1440")
        row.reservation_minutes = mins
    if payload.get("rotate_preview_token"):
        row.preview_token = new_secret_token(24)
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


def domain_display_status(row: m.EcommerceDomain) -> str:
    if row.status == "failed":
        return "failed"
    if row.status == "verified" and row.https_ready:
        return "active"
    if row.status == "verified":
        return "configuring"
    return "pending"


def serialize_domain(row: m.EcommerceDomain, *, include_secrets: bool = True) -> dict[str, Any]:
    payload = {
        "id": row.id,
        "hostname": row.hostname,
        "status": row.status,
        "display_status": domain_display_status(row),
        "https_ready": bool(row.https_ready),
        "is_primary": bool(row.is_primary),
        "redirect_to_id": row.redirect_to_id,
        "verified_at": row.verified_at.isoformat() if row.verified_at else None,
        "dns_instructions": (
            f"At your DNS host, create A or CNAME for {row.hostname} pointing at this "
            "application's public address, plus TXT "
            f"{TXT_PREFIX}<token>. Do not change DNS for an existing website; connect that site with the connector."
        ),
    }
    if include_secrets:
        payload["verification_token"] = row.verification_token
        payload["txt_record"] = f"{TXT_PREFIX}{row.verification_token}"
        payload["dns_instructions"] = (
            f"At your DNS host, create A or CNAME for {row.hostname} pointing at this "
            f"application's public address, plus TXT {TXT_PREFIX}{row.verification_token}. "
            "Do not change DNS for an existing website; connect that site with the connector."
        )
    return payload


async def list_domains(db: AsyncSession, tenant_id: str) -> list[m.EcommerceDomain]:
    return list(
        (
            await db.execute(
                select(m.EcommerceDomain)
                .where(m.EcommerceDomain.tenant_id == tenant_id)
                .order_by(m.EcommerceDomain.created_at)
            )
        ).scalars().all()
    )


async def add_domain(db: AsyncSession, *, tenant: m.Tenant, hostname: str) -> m.EcommerceDomain:
    assert_ecommerce_entitled(tenant)
    host = assert_public_hostname(hostname_from_website(hostname))
    existing = (
        await db.execute(select(m.EcommerceDomain).where(m.EcommerceDomain.hostname == host))
    ).scalar_one_or_none()
    if existing:
        if existing.tenant_id != tenant.id:
            raise HTTPException(status_code=409, detail="That domain is already used by another company")
        return existing
    others = await list_domains(db, tenant.id)
    row = m.EcommerceDomain(
        tenant_id=tenant.id,
        hostname=host,
        status="pending",
        verification_token=new_secret_token(18),
        is_primary=not others,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="That domain is already used by another company") from exc
    return row


async def _lookup_txt(hostname: str) -> list[str]:
    if _dns_lookup is not None:
        found = _dns_lookup(hostname)
        if hasattr(found, "__await__"):
            found = await found  # type: ignore[misc]
        return [str(x).strip().strip('"') for x in (found or [])]
    try:
        import dns.resolver  # type: ignore

        answers = dns.resolver.resolve(hostname, "TXT")
        records: list[str] = []
        for item in answers:
            records.extend(part.decode() if isinstance(part, bytes) else str(part) for part in item.strings)
        return [r.strip().strip('"') for r in records]
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "DOMAIN_DNS_BLOCKED",
                "message": (
                    "TXT lookup did not confirm this hostname. Add the verification "
                    "record at your DNS host, then verify again. Live DNS is an owner task."
                ),
            },
        )


async def verify_domain(db: AsyncSession, *, tenant_id: str, domain_id: str) -> m.EcommerceDomain:
    row = await db.get(m.EcommerceDomain, domain_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Domain not found")
    records = await _lookup_txt(row.hostname)
    expected = f"{TXT_PREFIX}{row.verification_token}"
    if expected not in records:
        if row.status == "verified":
            row.status = "failed"
            row.https_ready = False
            row.verification_token = new_secret_token(18)
            await db.flush()
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "DOMAIN_OWNERSHIP_CHANGED",
                    "message": "TXT no longer matches. Verification is required again with the new token.",
                    "expected": f"{TXT_PREFIX}{row.verification_token}",
                },
            )
        raise HTTPException(
            status_code=400,
            detail={
                "code": "DOMAIN_NOT_VERIFIED",
                "message": "TXT record does not match the verification token for this hostname.",
                "expected": expected,
            },
        )
    row.status = "verified"
    row.verified_at = datetime.utcnow()
    await db.flush()
    return row


async def mark_https_ready(
    db: AsyncSession, *, tenant_id: str, domain_id: str, ready: bool = True
) -> m.EcommerceDomain:
    row = await db.get(m.EcommerceDomain, domain_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Domain not found")
    if row.status != "verified":
        raise HTTPException(status_code=400, detail="Verify the domain before marking HTTPS ready")
    row.https_ready = bool(ready)
    await db.flush()
    return row


async def set_primary_domain(db: AsyncSession, *, tenant_id: str, domain_id: str) -> m.EcommerceDomain:
    row = await db.get(m.EcommerceDomain, domain_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Domain not found")
    if row.status != "verified":
        raise HTTPException(status_code=400, detail="Only a verified domain can be primary")
    for other in await list_domains(db, tenant_id):
        other.is_primary = other.id == row.id
        if other.id != row.id and other.redirect_to_id is None:
            other.redirect_to_id = row.id
    row.redirect_to_id = None
    await db.flush()
    return row


async def set_redirect_domain(
    db: AsyncSession, *, tenant_id: str, domain_id: str, redirect_to_id: str | None
) -> m.EcommerceDomain:
    row = await db.get(m.EcommerceDomain, domain_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Domain not found")
    if redirect_to_id:
        target = await db.get(m.EcommerceDomain, redirect_to_id)
        if target is None or target.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Redirect domain not found")
        if target.id == row.id:
            raise HTTPException(status_code=400, detail="A domain cannot redirect to itself")
        row.redirect_to_id = target.id
        row.is_primary = False
    else:
        row.redirect_to_id = None
    await db.flush()
    return row


async def remove_domain(db: AsyncSession, *, tenant_id: str, domain_id: str) -> None:
    row = await db.get(m.EcommerceDomain, domain_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Domain not found")
    others = [item for item in await list_domains(db, tenant_id) if item.id != row.id]
    for other in others:
        if other.redirect_to_id == row.id:
            other.redirect_to_id = None
    was_primary = bool(row.is_primary)
    await db.delete(row)
    await db.flush()
    if was_primary:
        successor = next((item for item in others if item.status == "verified"), others[0] if others else None)
        if successor is not None:
            successor.is_primary = True
            await db.flush()


def preview_token_digest(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def preview_tokens_match(stored: str | None, offered: str | None) -> bool:
    left = (stored or "").strip()
    right = (offered or "").strip()
    if not left or not right:
        return False
    if len(left) == len(right) and hmac.compare_digest(left, right):
        return True
    digest = preview_token_digest(right)
    if len(left) == len(digest):
        return hmac.compare_digest(left, digest)
    return False


async def resolve_public_tenant(
    db: AsyncSession,
    *,
    host: str | None,
    forwarded_host: str | None,
    preview_token: str | None,
    peer_ip: str | None = None,
) -> tuple[m.Tenant, m.EcommerceStorefront, m.EcommerceDomain | None]:
    token = (preview_token or "").strip()
    if token:
        digest = preview_token_digest(token)
        storefront = (
            await db.execute(
                select(m.EcommerceStorefront).where(
                    m.EcommerceStorefront.preview_token.in_((token, digest))
                )
            )
        ).scalar_one_or_none()
        if storefront is None or not preview_tokens_match(storefront.preview_token, token):
            raise HTTPException(status_code=404, detail="Preview is not available")
        tenant = await get_tenant(db, storefront.tenant_id)
        assert_ecommerce_entitled(tenant)
        return tenant, storefront, None

    hostname = host_from_request(host=host, forwarded_host=forwarded_host, peer_ip=peer_ip)
    if not hostname:
        raise HTTPException(
            status_code=404,
            detail={"code": "STOREFRONT_HOST_UNKNOWN", "message": "This host is not a company storefront."},
        )
    domain = (
        await db.execute(select(m.EcommerceDomain).where(m.EcommerceDomain.hostname == hostname))
    ).scalar_one_or_none()
    if domain is None or domain.status != "verified":
        raise HTTPException(
            status_code=404,
            detail={"code": "STOREFRONT_HOST_UNKNOWN", "message": "This host is not a company storefront."},
        )
    tenant = await get_tenant(db, domain.tenant_id)
    assert_ecommerce_entitled(tenant)
    storefront = await require_storefront(db, tenant.id)
    if not storefront.is_enabled:
        raise HTTPException(status_code=404, detail="This store is not open")
    return tenant, storefront, domain


async def listing_for_product(
    db: AsyncSession, tenant_id: str, product_id: str
) -> m.EcommerceListing | None:
    return (
        await db.execute(
            select(m.EcommerceListing).where(
                m.EcommerceListing.tenant_id == tenant_id,
                m.EcommerceListing.product_id == product_id,
            )
        )
    ).scalar_one_or_none()


async def upsert_listing(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    product_id: str,
    is_published: bool | None = None,
    online_price: float | None = None,
    stock_buffer: float | None = None,
    fulfillment_warehouse_id: str | None = None,
    clear_warehouse: bool = False,
    external_id: str | None = None,
) -> m.EcommerceListing:
    assert_ecommerce_entitled(tenant)
    product = await db.get(m.Product, product_id)
    if product is None or product.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Product not found")
    row = await listing_for_product(db, tenant.id, product.id)
    if row is None:
        row = m.EcommerceListing(tenant_id=tenant.id, product_id=product.id, is_published=False)
        db.add(row)
        await db.flush()
    if is_published is not None:
        row.is_published = bool(is_published)
    if online_price is not None:
        price = money_json(online_price)
        if price < 0:
            raise HTTPException(status_code=400, detail="Online price cannot be negative")
        row.online_price = price
    if stock_buffer is not None:
        buf = money_json(stock_buffer)
        if buf < 0:
            raise HTTPException(status_code=400, detail="Stock buffer cannot be negative")
        row.stock_buffer = buf
    if clear_warehouse:
        row.fulfillment_warehouse_id = None
    elif fulfillment_warehouse_id:
        wh = await db.get(m.Warehouse, fulfillment_warehouse_id)
        if wh is None or wh.tenant_id != tenant.id:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        row.fulfillment_warehouse_id = wh.id
    if external_id:
        row.external_id = str(external_id)[:80]
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def fulfillment_warehouse(
    db: AsyncSession,
    *,
    tenant_id: str,
    storefront: m.EcommerceStorefront,
    listing: m.EcommerceListing | None = None,
) -> m.Warehouse:
    wid = (listing.fulfillment_warehouse_id if listing else None) or storefront.fulfillment_warehouse_id
    if wid:
        wh = await db.get(m.Warehouse, wid)
        if wh is not None and wh.tenant_id == tenant_id and wh.is_active:
            return wh
    row = (
        await db.execute(
            select(m.Warehouse)
            .where(m.Warehouse.tenant_id == tenant_id, m.Warehouse.is_active.is_(True))
            .order_by(m.Warehouse.code)
        )
    ).scalars().first()
    if row is None:
        raise HTTPException(
            status_code=400,
            detail="Set a fulfillment warehouse before selling online.",
        )
    return row


async def published_listings(
    db: AsyncSession,
    tenant_id: str,
    *,
    q: str | None = None,
    category: str | None = None,
    product_id: str | None = None,
) -> list[tuple[m.EcommerceListing, m.Product]]:
    rows = (
        await db.execute(
            select(m.EcommerceListing, m.Product)
            .join(m.Product, m.Product.id == m.EcommerceListing.product_id)
            .where(
                m.EcommerceListing.tenant_id == tenant_id,
                m.EcommerceListing.is_published.is_(True),
                m.Product.tenant_id == tenant_id,
                m.Product.is_active.is_(True),
            )
            .order_by(m.Product.name)
        )
    ).all()
    needle = (q or "").strip().lower()
    wanted = (category or "").strip().lower()
    wanted_id = (product_id or "").strip().lower()
    out: list[tuple[m.EcommerceListing, m.Product]] = []
    for listing, product in rows:
        if wanted_id and str(product.id).lower() != wanted_id:
            continue
        if wanted and (product.category or "").strip().lower() != wanted:
            continue
        if needle:
            hay = " ".join(
                part
                for part in (product.name, product.sku, product.description, product.category)
                if part
            ).lower()
            if needle not in hay:
                continue
        out.append((listing, product))
    return out


async def online_available(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str,
    product_id: str,
    stock_buffer: float,
) -> float:
    from app.reservations import available_qty

    avail = await available_qty(
        db, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product_id
    )
    return money_json(max(avail - money_json(stock_buffer or 0), 0))


def listing_price(
    product: m.Product, listing: m.EcommerceListing, variant: m.ProductVariant | None = None
) -> float:
    if listing.online_price is not None:
        return money_json(listing.online_price)
    if variant is not None and variant.selling_price is not None:
        return money_json(variant.selling_price or 0)
    return money_json(product.selling_price or 0)


async def serialize_catalog_item(
    db: AsyncSession,
    *,
    tenant_id: str,
    storefront: m.EcommerceStorefront,
    listing: m.EcommerceListing,
    product: m.Product,
) -> dict[str, Any]:
    warehouse = await fulfillment_warehouse(db, tenant_id=tenant_id, storefront=storefront, listing=listing)
    available = await online_available(
        db,
        tenant_id=tenant_id,
        warehouse_id=warehouse.id,
        product_id=product.id,
        stock_buffer=money_json(listing.stock_buffer or 0),
    )
    return {
        "product_id": product.id,
        "name": product.name,
        "sku": product.sku,
        "description": product.description,
        "category": product.category,
        "image_url": public_product_image_path(product.id) if product.image_url else None,
        "image_alt": product.name,
        "price": listing_price(product, listing),
        "available_qty": available,
        "in_stock": available > 1e-9,
        "variants": [
            {
                "id": variant.id,
                "name": variant.name,
                "sku": variant.sku,
                "price": listing_price(product, listing, variant),
                "size": variant.size,
                "color": variant.color,
            }
            for variant in (
                await db.execute(
                    select(m.ProductVariant).where(
                        m.ProductVariant.tenant_id == tenant_id,
                        m.ProductVariant.product_id == product.id,
                        m.ProductVariant.is_active.is_(True),
                    )
                )
            ).scalars().all()
        ],
    }


async def get_cart(db: AsyncSession, *, tenant_id: str, token: str) -> m.EcommerceCart:
    cart = (
        await db.execute(
            select(m.EcommerceCart).where(
                m.EcommerceCart.tenant_id == tenant_id,
                m.EcommerceCart.token == token,
            )
        )
    ).scalar_one_or_none()
    if cart is None or cart.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


async def create_cart(db: AsyncSession, tenant_id: str) -> m.EcommerceCart:
    cart = m.EcommerceCart(
        tenant_id=tenant_id,
        token=new_secret_token(24),
        expires_at=datetime.utcnow() + timedelta(hours=CART_HOURS),
    )
    db.add(cart)
    await db.flush()
    return cart


async def cart_items(db: AsyncSession, cart_id: str) -> list[m.EcommerceCartItem]:
    return list(
        (
            await db.execute(
                select(m.EcommerceCartItem).where(m.EcommerceCartItem.cart_id == cart_id)
            )
        ).scalars().all()
    )


async def serialize_cart(db: AsyncSession, cart: m.EcommerceCart) -> dict[str, Any]:
    items = await cart_items(db, cart.id)
    lines = []
    subtotal = 0.0
    for item in items:
        product = await db.get(m.Product, item.product_id)
        variant = await db.get(m.ProductVariant, item.variant_id) if item.variant_id else None
        line_total = money_json(money_json(item.unit_price) * money_json(item.quantity))
        subtotal += line_total
        lines.append(
            {
                "product_id": item.product_id,
                "variant_id": item.variant_id,
                "variant_name": variant.name if variant else None,
                "name": product.name if product else "Item",
                "image_url": public_product_image_path(product.id) if product and product.image_url else None,
                "quantity": money_json(item.quantity),
                "unit_price": money_json(item.unit_price),
                "line_total": line_total,
            }
        )
    return {
        "token": cart.token,
        "items": lines,
        "subtotal": money_json(subtotal),
        "expires_at": cart.expires_at.isoformat(),
    }


async def set_cart_item(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    storefront: m.EcommerceStorefront,
    cart: m.EcommerceCart,
    product_id: str,
    quantity: float,
    variant_id: str | None = None,
) -> m.EcommerceCart:
    qty = money_json(quantity)
    listing = await listing_for_product(db, tenant.id, product_id)
    product = await db.get(m.Product, product_id)
    if (
        listing is None
        or not listing.is_published
        or product is None
        or product.tenant_id != tenant.id
        or not product.is_active
    ):
        raise HTTPException(status_code=404, detail="Product is not for sale online")
    variant = None
    if variant_id:
        variant = await db.get(m.ProductVariant, str(variant_id))
        if variant is None or variant.tenant_id != tenant.id or variant.product_id != product.id:
            raise HTTPException(status_code=404, detail="Variant is not for sale online")
        if not variant.is_active:
            raise HTTPException(status_code=404, detail="Variant is not for sale online")
    warehouse = await fulfillment_warehouse(db, tenant_id=tenant.id, storefront=storefront, listing=listing)
    available = await online_available(
        db,
        tenant_id=tenant.id,
        warehouse_id=warehouse.id,
        product_id=product.id,
        stock_buffer=money_json(listing.stock_buffer or 0),
    )
    existing = (
        await db.execute(
            select(m.EcommerceCartItem).where(
                m.EcommerceCartItem.cart_id == cart.id,
                m.EcommerceCartItem.product_id == product.id,
                m.EcommerceCartItem.variant_id == (variant.id if variant else None),
            )
        )
    ).scalar_one_or_none()
    if qty <= 1e-9:
        if existing is not None:
            await db.delete(existing)
            await db.flush()
        return cart
    if available + 1e-9 < qty:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INSUFFICIENT_ONLINE_STOCK",
                "message": "Not enough stock for online sale (POS buffer reserved).",
                "available": available,
                "requested": qty,
            },
        )
    price = listing_price(product, listing, variant)
    if existing is None:
        db.add(
            m.EcommerceCartItem(
                tenant_id=tenant.id,
                cart_id=cart.id,
                product_id=product.id,
                variant_id=variant.id if variant else None,
                quantity=qty,
                unit_price=price,
            )
        )
    else:
        existing.quantity = qty
        existing.unit_price = price
    cart.updated_at = datetime.utcnow()
    await db.flush()
    return cart


async def next_order_number(db: AsyncSession, tenant_id: str) -> str:
    year = datetime.utcnow().year
    prefix = f"WEB{year}"
    count = money_json(
        (
            await db.execute(
                select(func.count()).select_from(m.EcommerceOrder).where(
                    m.EcommerceOrder.tenant_id == tenant_id,
                    m.EcommerceOrder.order_number.like(f"{prefix}%"),
                )
            )
        ).scalar()
        or 0
    )
    return f"{prefix}{int(count) + 1:04d}"


async def active_ecommerce_reserved_qty(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str,
    product_id: str,
    exclude_order_id: str | None = None,
) -> float:
    stmt = select(func.coalesce(func.sum(m.EcommerceReservation.quantity), 0)).where(
        m.EcommerceReservation.tenant_id == tenant_id,
        m.EcommerceReservation.warehouse_id == warehouse_id,
        m.EcommerceReservation.product_id == product_id,
        m.EcommerceReservation.status == "active",
        m.EcommerceReservation.expires_at > datetime.utcnow(),
    )
    if exclude_order_id:
        stmt = stmt.where(m.EcommerceReservation.order_id != exclude_order_id)
    return money_json((await db.execute(stmt)).scalar() or 0)


async def reserve_order_stock(
    db: AsyncSession,
    *,
    tenant_id: str,
    order: m.EcommerceOrder,
    items: list[m.EcommerceOrderItem],
    warehouse_id: str,
    storefront: m.EcommerceStorefront,
) -> None:
    from app.reservations import available_qty

    existing = (
        await db.execute(
            select(m.EcommerceReservation).where(
                m.EcommerceReservation.tenant_id == tenant_id,
                m.EcommerceReservation.order_id == order.id,
                m.EcommerceReservation.status == "active",
            )
        )
    ).scalars().all()
    if existing:
        return
    expires = datetime.utcnow() + timedelta(minutes=int(storefront.reservation_minutes or DEFAULT_RESERVE_MINUTES))
    for item in items:
        listing = await listing_for_product(db, tenant_id, item.product_id)
        buffer = money_json(listing.stock_buffer or 0) if listing else 0.0
        avail = await available_qty(
            db,
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            product_id=item.product_id,
        )
        sellable = money_json(max(avail - buffer, 0))
        qty = money_json(item.quantity)
        if sellable + 1e-9 < qty:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "INSUFFICIENT_ONLINE_STOCK",
                    "message": "Not enough stock for online sale (POS buffer reserved).",
                    "product_id": item.product_id,
                    "available": sellable,
                    "requested": qty,
                },
            )
        db.add(
            m.EcommerceReservation(
                tenant_id=tenant_id,
                order_id=order.id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                warehouse_id=warehouse_id,
                quantity=qty,
                status="active",
                expires_at=expires,
            )
        )
    order.reserved_until = expires
    await db.flush()


async def release_order_reservations(db: AsyncSession, *, tenant_id: str, order_id: str) -> int:
    rows = (
        await db.execute(
            select(m.EcommerceReservation).where(
                m.EcommerceReservation.tenant_id == tenant_id,
                m.EcommerceReservation.order_id == order_id,
                m.EcommerceReservation.status == "active",
            )
        )
    ).scalars().all()
    now = datetime.utcnow()
    for row in rows:
        row.status = "released"
        row.released_at = now
    await db.flush()
    return len(rows)


async def consume_order_reservations(db: AsyncSession, *, tenant_id: str, order_id: str) -> int:
    rows = (
        await db.execute(
            select(m.EcommerceReservation).where(
                m.EcommerceReservation.tenant_id == tenant_id,
                m.EcommerceReservation.order_id == order_id,
                m.EcommerceReservation.status == "active",
            )
        )
    ).scalars().all()
    now = datetime.utcnow()
    for row in rows:
        row.status = "consumed"
        row.consumed_at = now
    await db.flush()
    return len(rows)


async def checkout(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    storefront: m.EcommerceStorefront,
    cart: m.EcommerceCart,
    guest_name: str,
    guest_email: str | None,
    guest_phone: str | None,
    fulfillment: str,
    delivery_address: str | None,
    notes: str | None,
    shopper: m.EcommerceShopper | None = None,
) -> m.EcommerceOrder:
    if not storefront.is_enabled:
        raise HTTPException(status_code=404, detail="This store is not open")
    method = (fulfillment or "delivery").strip().lower()
    if method not in {"delivery", "pickup"}:
        raise HTTPException(status_code=400, detail="Fulfillment must be delivery or pickup")
    if method == "delivery" and not storefront.allow_delivery:
        raise HTTPException(status_code=400, detail="Delivery is not offered")
    if method == "pickup" and not storefront.allow_pickup:
        raise HTTPException(status_code=400, detail="Pickup is not offered")
    if shopper is not None:
        guest_name = guest_name or shopper.name
        guest_email = guest_email or shopper.email
    name = require_honest_narrative(guest_name, label="Customer name", min_length=1, max_length=180)
    items = await cart_items(db, cart.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    warehouse = await fulfillment_warehouse(db, tenant_id=tenant.id, storefront=storefront)
    address = None
    if method == "delivery":
        address = require_honest_narrative(
            delivery_address, label="Delivery address", min_length=4, max_length=500
        )
    order = m.EcommerceOrder(
        tenant_id=tenant.id,
        order_number=await next_order_number(db, tenant.id),
        tracking_token=new_secret_token(24),
        status="awaiting_payment",
        fulfillment=method,
        guest_name=name,
        guest_email=(guest_email or "").strip() or None,
        guest_phone=(guest_phone or "").strip() or None,
        delivery_address=address,
        notes=optional_honest_narrative(notes, label="Order notes"),
        currency=tenant.currency or "GHS",
        warehouse_id=warehouse.id,
        store_id=storefront.fulfillment_store_id,
        shopper_id=shopper.id if shopper else None,
        party_id=shopper.party_id if shopper else None,
    )
    db.add(order)
    await db.flush()
    subtotal = 0.0
    prepared: list[m.EcommerceOrderItem] = []
    for item in items:
        listing = await listing_for_product(db, tenant.id, item.product_id)
        product = await db.get(m.Product, item.product_id)
        if listing is None or not listing.is_published or product is None:
            raise HTTPException(status_code=409, detail="A cart item is no longer for sale online")
        qty = money_json(item.quantity)
        variant = await db.get(m.ProductVariant, item.variant_id) if item.variant_id else None
        price = listing_price(product, listing, variant)
        line_total = money_json(qty * price)
        subtotal += line_total
        line = m.EcommerceOrderItem(
            tenant_id=tenant.id,
            order_id=order.id,
            product_id=product.id,
            variant_id=item.variant_id,
            quantity=qty,
            unit_price=price,
            line_total=line_total,
        )
        db.add(line)
        prepared.append(line)
    order.subtotal = money_json(subtotal)
    order.tax_amount = 0
    order.total_amount = money_json(subtotal)
    await db.flush()
    await reserve_order_stock(
        db,
        tenant_id=tenant.id,
        order=order,
        items=prepared,
        warehouse_id=warehouse.id,
        storefront=storefront,
    )
    for item in items:
        await db.delete(item)
    cart.expires_at = datetime.utcnow()
    await db.flush()
    return order


async def get_order_by_tracking(
    db: AsyncSession, *, tenant_id: str, tracking_token: str
) -> m.EcommerceOrder:
    order = (
        await db.execute(
            select(m.EcommerceOrder).where(
                m.EcommerceOrder.tenant_id == tenant_id,
                m.EcommerceOrder.tracking_token == tracking_token,
            )
        )
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


async def get_order(db: AsyncSession, tenant_id: str, order_id: str) -> m.EcommerceOrder:
    order = await db.get(m.EcommerceOrder, order_id)
    if order is None or order.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


async def list_orders(db: AsyncSession, tenant_id: str) -> list[m.EcommerceOrder]:
    return list(
        (
            await db.execute(
                select(m.EcommerceOrder)
                .where(m.EcommerceOrder.tenant_id == tenant_id)
                .order_by(m.EcommerceOrder.created_at.desc())
            )
        ).scalars().all()
    )


def serialize_order(order: m.EcommerceOrder, items: list[m.EcommerceOrderItem] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": order.id,
        "order_number": order.order_number,
        "tracking_token": order.tracking_token,
        "status": order.status,
        "fulfillment": order.fulfillment,
        "guest_name": order.guest_name,
        "guest_email": order.guest_email,
        "delivery_address": order.delivery_address,
        "total_amount": money_json(order.total_amount),
        "currency": order.currency,
        "paid": order.status in PAID_ORDER_STATUSES and order.status != "returned",
        "sales_invoice_id": order.sales_invoice_id,
        "shopper_id": order.shopper_id,
        "reserved_until": order.reserved_until.isoformat() if order.reserved_until else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }
    if items is not None:
        payload["items"] = [
            {
                "product_id": item.product_id,
                "variant_id": item.variant_id,
                "quantity": money_json(item.quantity),
                "unit_price": money_json(item.unit_price),
                "line_total": money_json(item.line_total),
            }
            for item in items
        ]
    return payload


async def order_items(db: AsyncSession, order_id: str) -> list[m.EcommerceOrderItem]:
    return list(
        (
            await db.execute(
                select(m.EcommerceOrderItem).where(m.EcommerceOrderItem.order_id == order_id)
            )
        ).scalars().all()
    )


async def cancel_order(db: AsyncSession, *, tenant_id: str, order: m.EcommerceOrder) -> m.EcommerceOrder:
    if order.status in PAID_ORDER_STATUSES:
        raise HTTPException(status_code=409, detail="Paid orders cannot be cancelled here")
    if order.status in {"cancelled", "expired"}:
        return order
    await release_order_reservations(db, tenant_id=tenant_id, order_id=order.id)
    order.status = "cancelled"
    order.updated_at = datetime.utcnow()
    await db.flush()
    return order


async def expire_due_reservations(db: AsyncSession, tenant_id: str) -> int:
    now = datetime.utcnow()
    orders = (
        await db.execute(
            select(m.EcommerceOrder).where(
                m.EcommerceOrder.tenant_id == tenant_id,
                m.EcommerceOrder.status == "awaiting_payment",
                m.EcommerceOrder.reserved_until.is_not(None),
                m.EcommerceOrder.reserved_until <= now,
            )
        )
    ).scalars().all()
    count = 0
    for order in orders:
        await release_order_reservations(db, tenant_id=tenant_id, order_id=order.id)
        order.status = "expired"
        order.updated_at = now
        count += 1
    await db.flush()
    return count


async def ensure_guest_party(db: AsyncSession, *, tenant_id: str, order: m.EcommerceOrder) -> m.Party:
    if order.party_id:
        party = await db.get(m.Party, order.party_id)
        if party is not None and party.tenant_id == tenant_id:
            return party
    email = (order.guest_email or "").strip().lower() or None
    if email:
        existing = (
            await db.execute(
                select(m.Party).where(
                    m.Party.tenant_id == tenant_id,
                    m.Party.kind == "customer",
                    m.Party.email == email,
                )
            )
        ).scalars().first()
        if existing is not None:
            order.party_id = existing.id
            return existing
    # Phone-only shoppers: reuse the customer with the same phone instead of adding a duplicate every order.
    phone = (order.guest_phone or "").strip() or None
    if phone and not email:
        existing = (
            await db.execute(
                select(m.Party)
                .where(
                    m.Party.tenant_id == tenant_id,
                    m.Party.kind == "customer",
                    m.Party.phone == phone,
                )
                .order_by(m.Party.id)
            )
        ).scalars().first()
        if existing is not None:
            order.party_id = existing.id
            return existing
    party = m.Party(
        tenant_id=tenant_id,
        kind="customer",
        name=order.guest_name,
        email=email,
        phone=order.guest_phone,
        address=order.delivery_address,
        profile_type="registered",
        category="online",
        credit_limit=0,
    )
    db.add(party)
    await db.flush()
    order.party_id = party.id
    return party


async def post_paid_order(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    order: m.EcommerceOrder,
    payment_method: str = "card",
    payment_reference: str | None = None,
) -> m.EcommerceOrder:
    if order.sales_invoice_id:
        return order
    if order.status in {"cancelled", "expired"}:
        raise HTTPException(status_code=409, detail="This order is no longer open")
    items = await order_items(db, order.id)
    if not items:
        raise HTTPException(status_code=400, detail="Order has no lines")
    await consume_order_reservations(db, tenant_id=tenant.id, order_id=order.id)
    party = await ensure_guest_party(db, tenant_id=tenant.id, order=order)
    from app.sales import create_sales_invoice, post_sales_invoice, record_customer_payment

    staff_id = (
        await db.execute(
            select(m.User.id).where(
                m.User.tenant_id == tenant.id,
                m.User.role == "company_admin",
                m.User.is_active.is_(True),
            )
        )
    ).scalars().first() or "system"
    invoice = await create_sales_invoice(
        db,
        tenant_id=tenant.id,
        user_id=staff_id,
        customer_id=party.id,
        items=[
            {"product_id": item.product_id, "quantity": money_json(item.quantity), "unit_price": money_json(item.unit_price)}
            for item in items
        ],
        notes=f"Online order {order.order_number}",
        store_id=order.store_id,
        sales_channel="retail",
    )
    invoice = await post_sales_invoice(
        db,
        tenant_id=tenant.id,
        user_id=staff_id,
        invoice_id=invoice.id,
    )
    await record_customer_payment(
        db,
        tenant_id=tenant.id,
        user_id=staff_id,
        customer_id=party.id,
        amount=money_json(order.total_amount),
        sales_invoice_id=invoice.id,
        payment_method=payment_method,
        reference=payment_reference or order.payment_reference,
        notes=f"Storefront {order.order_number}",
    )
    order.sales_invoice_id = invoice.id
    order.status = "paid"
    order.paid_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()
    if order.shopper_id:
        shopper = await db.get(m.EcommerceShopper, order.shopper_id)
        if shopper is not None and shopper.tenant_id == tenant.id:
            shopper.party_id = party.id
    await db.flush()
    from app import ecommerce_connectors as connectors_svc

    await connectors_svc.push_order_and_stock(db, tenant=tenant, order=order)
    return order


def _normalized_fulfillment_status(status: str) -> str:
    if status == "fulfilled":
        return "delivered"
    return status


async def advance_fulfillment(
    db: AsyncSession,
    *,
    tenant_id: str,
    order: m.EcommerceOrder,
    target: str | None = None,
) -> m.EcommerceOrder:
    if order.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Order not found")
    current = _normalized_fulfillment_status(order.status)
    if current not in FULFILLMENT_STEPS:
        raise HTTPException(status_code=409, detail="Only a paid order can be packed, dispatched, or delivered")
    if target:
        wanted = _normalized_fulfillment_status(str(target).strip().lower())
        if wanted not in FULFILLMENT_STEPS:
            raise HTTPException(status_code=400, detail="Fulfillment step must be packed, dispatched, or delivered")
        expected = FULFILLMENT_STEPS[FULFILLMENT_STEPS.index(current) + 1] if current != "delivered" else "delivered"
        if wanted != expected and wanted != current:
            raise HTTPException(status_code=409, detail=f"Next fulfillment step is {expected}")
        if wanted == current:
            return order
        order.status = wanted
    else:
        if current == "delivered":
            return order
        order.status = FULFILLMENT_STEPS[FULFILLMENT_STEPS.index(current) + 1]
    order.updated_at = datetime.utcnow()
    await db.flush()
    from app import ecommerce_connectors as connectors_svc

    await connectors_svc.push_order_and_stock(db, tenant=await get_tenant(db, tenant_id), order=order)
    return order


async def fulfill_order(db: AsyncSession, *, tenant_id: str, order: m.EcommerceOrder) -> m.EcommerceOrder:
    return await advance_fulfillment(db, tenant_id=tenant_id, order=order)


async def return_paid_order(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    order: m.EcommerceOrder,
    user_id: str,
    reason: str = "customer_change",
) -> m.EcommerceOrder:
    current = _normalized_fulfillment_status(order.status)
    if current == "returned":
        return order
    if current not in FULFILLMENT_STEPS:
        raise HTTPException(status_code=409, detail="Only a paid online order can be returned")
    if not order.sales_invoice_id:
        raise HTTPException(status_code=409, detail="This order has no posted invoice to return")
    items = await order_items(db, order.id)
    if not items:
        raise HTTPException(status_code=400, detail="Order has no lines")
    from app.sales_docs import create_return, post_return

    ret = await create_return(
        db,
        tenant_id=tenant.id,
        user_id=user_id,
        sales_invoice_id=order.sales_invoice_id,
        reason=reason,
        restock=True,
        notes=f"Online order {order.order_number}",
        items=[
            {"product_id": item.product_id, "quantity": money_json(item.quantity), "condition": "sellable"}
            for item in items
        ],
    )
    await post_return(
        db,
        tenant_id=tenant.id,
        user_id=user_id,
        return_id=ret.id,
        settlement_method="refund",
        payment_method="card",
    )
    order.status = "returned"
    order.updated_at = datetime.utcnow()
    await db.flush()
    from app import ecommerce_connectors as connectors_svc

    await connectors_svc.push_order_and_stock(db, tenant=tenant, order=order)
    return order


async def serialize_ecommerce_health(db: AsyncSession, tenant: m.Tenant) -> dict[str, Any]:
    """Platform-owner view: domain and connector health, never credentials."""
    from app import ecommerce_connectors as connectors_svc
    from app import ecommerce_payments as payments_svc

    entitled = True
    try:
        assert_ecommerce_entitled(tenant)
    except HTTPException:
        entitled = False
    storefront = (
        await db.execute(select(m.EcommerceStorefront).where(m.EcommerceStorefront.tenant_id == tenant.id))
    ).scalar_one_or_none()
    domains = [serialize_domain(row, include_secrets=False) for row in await list_domains(db, tenant.id)]
    connectors = [
        {
            "platform": row.platform,
            "enabled": bool(row.is_enabled),
            "implemented": row.platform in IMPLEMENTED_CONNECTORS,
            "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
            "last_error": row.last_error,
            "credentials_configured": bool(row.credentials_enc),
        }
        for row in await connectors_svc.list_connectors(db, tenant.id)
    ]
    gateway = payments_svc.serialize_gateway(await payments_svc.get_gateway(db, tenant.id))
    open_orders = money_json(
        (
            await db.execute(
                select(func.count()).select_from(m.EcommerceOrder).where(
                    m.EcommerceOrder.tenant_id == tenant.id,
                    m.EcommerceOrder.status == "awaiting_payment",
                )
            )
        ).scalar()
        or 0
    )
    return {
        "entitled": entitled,
        "storefront_enabled": bool(storefront and storefront.is_enabled),
        "has_logo": bool(storefront and storefront.logo_url),
        "has_banner": bool(storefront and storefront.banner_url),
        "has_favicon": bool(storefront and storefront.favicon_url),
        "domains": domains,
        "connectors": connectors,
        "gateway": {
            "configured": gateway.get("configured"),
            "provider": gateway.get("provider"),
            "mode": gateway.get("mode"),
            "last_test_ok": gateway.get("last_test_ok"),
        },
        "open_orders": int(open_orders),
    }


SHOPPER_HOURS = 24


def serialize_shopper(row: m.EcommerceShopper) -> dict[str, Any]:
    return {
        "id": row.id,
        "email": row.email,
        "name": row.name,
        "session_token": row.session_token,
        "expires_at": row.session_expires_at.isoformat() if row.session_expires_at else None,
    }


async def get_shopper_by_session(
    db: AsyncSession, *, tenant_id: str, token: str | None
) -> m.EcommerceShopper | None:
    raw = (token or "").strip()
    if not raw:
        return None
    row = (
        await db.execute(
            select(m.EcommerceShopper).where(
                m.EcommerceShopper.tenant_id == tenant_id,
                m.EcommerceShopper.session_token == raw,
            )
        )
    ).scalar_one_or_none()
    if row is None or not row.session_expires_at or row.session_expires_at < datetime.utcnow():
        return None
    return row


async def register_shopper(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    name: str,
    email: str,
    password: str,
) -> m.EcommerceShopper:
    from app.security import hash_password, validate_password_strength

    assert_ecommerce_entitled(tenant)
    clean_email = (email or "").strip().lower()
    if "@" not in clean_email:
        raise HTTPException(status_code=400, detail="A valid email is required")
    existing = (
        await db.execute(
            select(m.EcommerceShopper).where(
                m.EcommerceShopper.tenant_id == tenant.id,
                m.EcommerceShopper.email == clean_email,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account already exists for this email")
    staff = (
        await db.execute(
            select(m.User.id).where(
                m.User.tenant_id == tenant.id,
                m.User.email == clean_email,
            )
        )
    ).scalar_one_or_none()
    if staff is not None:
        raise HTTPException(status_code=409, detail="This email belongs to a staff account")
    validate_password_strength(password)
    row = m.EcommerceShopper(
        tenant_id=tenant.id,
        email=clean_email,
        password_hash=hash_password(password),
        name=require_honest_narrative(name, label="Customer name", min_length=1, max_length=180),
        session_token=new_secret_token(24),
        session_expires_at=datetime.utcnow() + timedelta(hours=SHOPPER_HOURS),
    )
    db.add(row)
    await db.flush()
    return row


async def login_shopper(
    db: AsyncSession, *, tenant: m.Tenant, email: str, password: str
) -> m.EcommerceShopper:
    from app.security import verify_password

    assert_ecommerce_entitled(tenant)
    clean_email = (email or "").strip().lower()
    row = (
        await db.execute(
            select(m.EcommerceShopper).where(
                m.EcommerceShopper.tenant_id == tenant.id,
                m.EcommerceShopper.email == clean_email,
            )
        )
    ).scalar_one_or_none()
    if row is None or not verify_password(password, row.password_hash):
        raise HTTPException(status_code=401, detail="Invalid storefront email or password")
    row.session_token = new_secret_token(24)
    row.session_expires_at = datetime.utcnow() + timedelta(hours=SHOPPER_HOURS)
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def logout_shopper(db: AsyncSession, shopper: m.EcommerceShopper) -> None:
    shopper.session_token = None
    shopper.session_expires_at = None
    shopper.updated_at = datetime.utcnow()
    await db.flush()


async def shopper_orders(db: AsyncSession, shopper: m.EcommerceShopper) -> list[m.EcommerceOrder]:
    return list(
        (
            await db.execute(
                select(m.EcommerceOrder)
                .where(
                    m.EcommerceOrder.tenant_id == shopper.tenant_id,
                    m.EcommerceOrder.shopper_id == shopper.id,
                )
                .order_by(m.EcommerceOrder.created_at.desc())
            )
        ).scalars().all()
    )
