"""Staff ecommerce controls and public storefront routes."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import ecommerce as ecom
from app import ecommerce_connectors as connectors_svc
from app import ecommerce_payments as payments_svc
from app import storage as storage_svc
from app import logo_media as logo_media_svc
from app.config import settings
from app.db import get_db
from app.honesty import money_json
from app.schemas import (
    AddressValue,
    CatalogSearchValue,
    E164PhoneValue,
    PartyNameValue,
    ProductCategoryLabelValue,
    ProductDescriptionValue,
    ProductNameValue,
    StorefrontPolicyValue,
    StorefrontSecretTokenValue,
    UserPasswordValue,
    UuidIdValue,
    WebhookUrlValue,
    WebsiteHostnameValue,
)
from app import models as m
from app.security import require_permission

staff = APIRouter(prefix="/ecommerce", tags=["ecommerce"])
storefront = APIRouter(prefix="/storefront", tags=["storefront"])


def env(data=None, message: str = "Operation completed successfully"):
    return {"success": True, "data": data, "message": message}


class StorefrontUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_enabled: bool | None = None
    tagline: ProductNameValue | None = None
    announcement: ProductDescriptionValue | None = None
    support_email: EmailStr | None = None
    support_phone: E164PhoneValue | None = None
    fulfillment_warehouse_id: UuidIdValue | None = None
    fulfillment_store_id: UuidIdValue | None = None
    allow_delivery: bool | None = None
    allow_pickup: bool | None = None
    pickup_address: AddressValue | None = None
    delivery_notes: ProductDescriptionValue | None = None
    policy_shipping: StorefrontPolicyValue | None = None
    policy_returns: StorefrontPolicyValue | None = None
    policy_privacy: StorefrontPolicyValue | None = None
    reservation_minutes: int | None = Field(default=None, ge=5, le=1440)
    rotate_preview_token: bool | None = None


class DomainCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: WebsiteHostnameValue


class DomainRedirect(BaseModel):
    model_config = ConfigDict(extra="forbid")

    redirect_to_id: UuidIdValue | None = None


class ListingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    is_published: bool | None = None
    online_price: float | None = Field(default=None, ge=0)
    stock_buffer: float | None = Field(default=None, ge=0)
    fulfillment_warehouse_id: UuidIdValue | None = None
    clear_warehouse: bool | None = None


class GatewayUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["mock", "paystack", "flutterwave"]
    mode: Literal["test", "live"] = "test"
    secret: str | None = Field(default=None, min_length=1, max_length=200)
    webhook_secret: str | None = Field(default=None, min_length=1, max_length=200)
    public_key: str | None = Field(default=None, max_length=200)


class ConnectorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Literal["woocommerce", "shopify", "squarespace", "magento", "custom"]
    store_url: WebhookUrlValue | None = None
    consumer_key: str | None = None
    consumer_secret: str | None = None
    enabled: bool | None = None


class SyncBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["products", "orders"] = "products"


class CartItemBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: float = Field(ge=0)
    variant_id: UuidIdValue | None = None


class ShopperRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: PartyNameValue
    email: EmailStr
    password: UserPasswordValue


class ShopperLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: UserPasswordValue


class CheckoutBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cart_token: StorefrontSecretTokenValue
    guest_name: PartyNameValue | None = None
    guest_email: EmailStr | None = None
    guest_phone: E164PhoneValue | None = None
    fulfillment: Literal["delivery", "pickup"] = "delivery"
    delivery_address: AddressValue | None = None
    notes: ProductDescriptionValue | None = None


async def _staff_tenant(db: AsyncSession, claims: dict):
    tenant = await ecom.get_tenant(db, claims["tenant_id"])
    ecom.assert_ecommerce_entitled(tenant)
    return tenant


def _public_preview(request: Request, preview_token: str | None) -> str | None:
    return preview_token or request.headers.get("x-storefront-preview") or request.query_params.get("preview_token")


def _shopper_token(request: Request) -> str | None:
    return request.headers.get("x-storefront-shopper") or request.query_params.get("shopper_token")


@staff.get("")
async def staff_get_storefront(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "read")),
):
    tenant = await _staff_tenant(db, claims)
    row = await ecom.require_storefront(db, tenant.id)
    domains = [ecom.serialize_domain(d) for d in await ecom.list_domains(db, tenant.id)]
    return env(
        {
            "storefront": ecom.serialize_storefront(row, tenant),
            "domains": domains,
            "gateway": payments_svc.serialize_gateway(await payments_svc.get_gateway(db, tenant.id)),
        }
    )


@staff.patch("")
async def staff_update_storefront(
    payload: StorefrontUpdate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    row = await ecom.update_storefront(db, tenant=tenant, payload=payload.model_dump(exclude_unset=True))
    await db.commit()
    return env(ecom.serialize_storefront(row, tenant))


@staff.post("/media/{kind}")
async def staff_upload_media(
    kind: Literal["logo", "banner", "favicon"],
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    stored = await storage_svc.save_upload(
        tenant_id=tenant.id,
        category=f"ecommerce_{kind}",
        upload=file,
        allowed_types=storage_svc.LOGO_CONTENT_TYPES,
        max_bytes=int(settings.MEDIA_MAX_LOGO_BYTES),
    )
    row = await ecom.set_storefront_media(db, tenant=tenant, kind=kind, storage_key=stored.key)
    await audit_svc.record_event(
        db,
        tenant_id=tenant.id,
        user_id=claims["sub"],
        module="settings",
        action=f"storefront_{kind}_upload",
        entity="ecommerce_storefront",
        entity_id=row.id,
        details={"key": stored.key, "size": stored.size, "content_type": stored.content_type},
    )
    await db.commit()
    return env(
        {
            **ecom.serialize_storefront(row, tenant),
            "uploaded": {
                "kind": kind,
                "size": stored.size,
                "content_type": stored.content_type,
                "filename": stored.original_filename,
            },
        },
        f"Storefront {kind} uploaded. This is separate from the ERP sidebar logo.",
    )


@staff.get("/media/{kind}")
async def staff_get_media(
    kind: Literal["logo", "banner", "favicon"],
    request: Request,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "read")),
):
    tenant = await _staff_tenant(db, claims)
    row = await ecom.require_storefront(db, tenant.id)
    key = getattr(row, ecom.storefront_media_attr(kind))
    if not key:
        raise HTTPException(status_code=404, detail=f"No storefront {kind} uploaded")
    return logo_media_svc.keyed_media_response(
        key,
        tenant_id=tenant.id,
        request=request,
        cache_control=logo_media_svc.REVALIDATE_CACHE_CONTROL,
        vary="Authorization, X-Tenant-ID",
    )


@staff.delete("/media/{kind}")
async def staff_delete_media(
    kind: Literal["logo", "banner", "favicon"],
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    row = await ecom.clear_storefront_media(db, tenant=tenant, kind=kind)
    await audit_svc.record_event(
        db,
        tenant_id=tenant.id,
        user_id=claims["sub"],
        module="settings",
        action=f"storefront_{kind}_delete",
        entity="ecommerce_storefront",
        entity_id=row.id,
    )
    await db.commit()
    return env(ecom.serialize_storefront(row, tenant), f"Storefront {kind} removed")


@staff.post("/domains")
async def staff_add_domain(
    payload: DomainCreate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    row = await ecom.add_domain(db, tenant=tenant, hostname=payload.hostname)
    await db.commit()
    return env(ecom.serialize_domain(row), "Add the TXT record, then verify.")


@staff.post("/domains/{domain_id}/verify")
async def staff_verify_domain(
    domain_id: UuidIdValue,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    try:
        row = await ecom.verify_domain(db, tenant_id=tenant.id, domain_id=domain_id)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        if detail.get("code") == "DOMAIN_OWNERSHIP_CHANGED":
            await db.commit()
        raise
    await db.commit()
    return env(ecom.serialize_domain(row), "Domain verified.")


@staff.post("/domains/{domain_id}/https-ready")
async def staff_https_ready(
    domain_id: UuidIdValue,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    row = await ecom.mark_https_ready(db, tenant_id=tenant.id, domain_id=domain_id, ready=True)
    await db.commit()
    return env(ecom.serialize_domain(row), "HTTPS-ready recorded. Certificates stay an owner task.")


@staff.post("/domains/{domain_id}/primary")
async def staff_primary_domain(
    domain_id: UuidIdValue,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    row = await ecom.set_primary_domain(db, tenant_id=tenant.id, domain_id=domain_id)
    await db.commit()
    return env(ecom.serialize_domain(row))


@staff.post("/domains/{domain_id}/redirect")
async def staff_redirect_domain(
    domain_id: UuidIdValue,
    payload: DomainRedirect,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    row = await ecom.set_redirect_domain(
        db, tenant_id=tenant.id, domain_id=domain_id, redirect_to_id=payload.redirect_to_id
    )
    await db.commit()
    return env(ecom.serialize_domain(row))


@staff.delete("/domains/{domain_id}")
async def staff_remove_domain(
    domain_id: UuidIdValue,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    await ecom.remove_domain(db, tenant_id=tenant.id, domain_id=domain_id)
    await db.commit()
    return env({"id": domain_id}, "Website unlinked.")


@staff.get("/listings")
async def staff_listings(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "read")),
):
    from sqlalchemy import select

    tenant = await _staff_tenant(db, claims)
    storefront_row = await ecom.require_storefront(db, tenant.id)
    products = (
        await db.execute(select(m.Product).where(m.Product.tenant_id == tenant.id).order_by(m.Product.name))
    ).scalars().all()
    data = []
    for product in products:
        listing = await ecom.listing_for_product(db, tenant.id, product.id)
        data.append(
            {
                "product_id": product.id,
                "name": product.name,
                "sku": product.sku,
                "category": product.category,
                "selling_price": money_json(product.selling_price or 0),
                "published": bool(listing and listing.is_published),
                "online_price": money_json(listing.online_price) if listing and listing.online_price is not None else None,
                "stock_buffer": money_json(listing.stock_buffer) if listing else 0,
                "fulfillment_warehouse_id": listing.fulfillment_warehouse_id if listing else None,
            }
        )
    return env({"items": data, "warehouse_id": storefront_row.fulfillment_warehouse_id})


@staff.put("/listings")
async def staff_upsert_listing(
    payload: ListingUpdate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    listing = await ecom.upsert_listing(
        db,
        tenant=tenant,
        product_id=payload.product_id,
        is_published=payload.is_published,
        online_price=payload.online_price,
        stock_buffer=payload.stock_buffer,
        fulfillment_warehouse_id=payload.fulfillment_warehouse_id,
        clear_warehouse=bool(payload.clear_warehouse),
    )
    await db.commit()
    return env(
        {
            "product_id": listing.product_id,
            "published": listing.is_published,
            "online_price": money_json(listing.online_price) if listing.online_price is not None else None,
            "stock_buffer": money_json(listing.stock_buffer or 0),
        }
    )


@staff.get("/orders")
async def staff_orders(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "read")),
):
    tenant = await _staff_tenant(db, claims)
    rows = await ecom.list_orders(db, tenant.id)
    # Staff see who ordered and what: phone and a short item list (the public tracking page does not get the phone).
    summaries: dict[str, list[str]] = {}
    if rows:
        lines = (
            await db.execute(
                select(m.EcommerceOrderItem.order_id, m.EcommerceOrderItem.quantity, m.Product.name)
                .join(m.Product, m.Product.id == m.EcommerceOrderItem.product_id)
                .where(
                    m.EcommerceOrderItem.tenant_id == tenant.id,
                    m.EcommerceOrderItem.order_id.in_([row.id for row in rows]),
                )
            )
        ).all()
        for order_id, qty, name in lines:
            qty_text = f"{money_json(qty):.3f}".rstrip("0").rstrip(".") or "0"
            summaries.setdefault(order_id, []).append(f"{name} × {qty_text}")
    return env(
        [
            {**ecom.serialize_order(row), "guest_phone": row.guest_phone, "items_summary": ", ".join(summaries.get(row.id, []))}
            for row in rows
        ]
    )


@staff.post("/orders/{order_id}/cancel")
async def staff_cancel_order(
    order_id: UuidIdValue,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    order = await ecom.cancel_order(db, tenant_id=tenant.id, order=await ecom.get_order(db, tenant.id, order_id))
    await db.commit()
    return env(ecom.serialize_order(order))


@staff.post("/orders/{order_id}/collect")
async def staff_collect_order(
    order_id: UuidIdValue,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    order = await ecom.get_order(db, tenant.id, order_id)
    order = await ecom.post_paid_order(db, tenant=tenant, order=order, payment_method="cash")
    await db.commit()
    return env(ecom.serialize_order(order), "Payment recorded and sales invoice posted once.")


@staff.post("/orders/{order_id}/fulfill")
async def staff_fulfill_order(
    order_id: UuidIdValue,
    target: Annotated[Literal["packed", "dispatched", "delivered"] | None, Query()] = None,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    order = await ecom.advance_fulfillment(
        db,
        tenant_id=tenant.id,
        order=await ecom.get_order(db, tenant.id, order_id),
        target=target,
    )
    await db.commit()
    return env(ecom.serialize_order(order))


@staff.post("/orders/{order_id}/return")
async def staff_return_order(
    order_id: UuidIdValue,
    reason: Annotated[
        Literal["damaged", "wrong_item", "defective", "customer_change", "other"], Query()
    ] = "customer_change",
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    order = await ecom.return_paid_order(
        db,
        tenant=tenant,
        order=await ecom.get_order(db, tenant.id, order_id),
        user_id=claims["sub"],
        reason=reason,
    )
    await db.commit()
    return env(ecom.serialize_order(order), "Return posted against the sales invoice.")


@staff.patch("/gateway")
async def staff_gateway(
    payload: GatewayUpdate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    row = await payments_svc.upsert_gateway(
        db,
        tenant=tenant,
        provider=payload.provider,
        mode=payload.mode,
        secret=payload.secret,
        webhook_secret=payload.webhook_secret,
        public_key=payload.public_key,
    )
    await db.commit()
    return env(payments_svc.serialize_gateway(row), "Secrets stored encrypted. Live charges stay off until a signed webhook succeeds.")


@staff.get("/connectors")
async def staff_connectors(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "read")),
):
    tenant = await _staff_tenant(db, claims)
    rows = await connectors_svc.list_connectors(db, tenant.id)
    jobs = [connectors_svc.serialize_sync_job(j) for j in await connectors_svc.list_sync_jobs(db, tenant.id)]
    return env({"connectors": [connectors_svc.serialize_connector(r) for r in rows], "jobs": jobs})


@staff.patch("/connectors")
async def staff_upsert_connector(
    payload: ConnectorUpdate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    row = await connectors_svc.upsert_connector(
        db,
        tenant=tenant,
        platform=payload.platform,
        store_url=payload.store_url,
        consumer_key=payload.consumer_key,
        consumer_secret=payload.consumer_secret,
        enabled=payload.enabled,
    )
    await db.commit()
    return env(connectors_svc.serialize_connector(row))


@staff.post("/connectors/{connector_id}/sync")
async def staff_sync_connector(
    connector_id: UuidIdValue,
    payload: SyncBody,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    connector = await db.get(m.EcommerceConnector, connector_id)
    if connector is None or connector.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Connector not found")
    job = await connectors_svc.run_connector_sync(db, tenant=tenant, connector=connector, kind=payload.kind)
    await db.commit()
    return env(connectors_svc.serialize_sync_job(job))


@staff.post("/connectors/retry")
async def staff_retry_connectors(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_permission("ecommerce", "write")),
):
    tenant = await _staff_tenant(db, claims)
    retried = await connectors_svc.retry_failed_syncs(db, tenant.id)
    await db.commit()
    jobs = [connectors_svc.serialize_sync_job(j) for j in await connectors_svc.list_sync_jobs(db, tenant.id)]
    return env({"retried": retried, "jobs": jobs})


# --- Public storefront (no ERP staff session) ---


@storefront.get("/bootstrap")
async def public_bootstrap(
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    q: Annotated[CatalogSearchValue | None, Query()] = None,
    category: Annotated[ProductCategoryLabelValue | None, Query()] = None,
    product_id: Annotated[UuidIdValue | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=48)] = 24,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, storefront_row, domain = await ecom.resolve_public_tenant(
        db,
        host=host,
        forwarded_host=x_forwarded_host,
        preview_token=_public_preview(request, preview_token),
    )
    redirect_host = None
    if domain and domain.redirect_to_id:
        target = await db.get(m.EcommerceDomain, domain.redirect_to_id)
        if target is not None and target.status == "verified":
            redirect_host = target.hostname
    published = await ecom.published_listings(
        db, tenant.id, q=q, category=category, product_id=product_id
    )
    total = len(published)
    start = (page - 1) * page_size
    page_rows = published[start : start + page_size]
    items = [
        await ecom.serialize_catalog_item(
            db, tenant_id=tenant.id, storefront=storefront_row, listing=listing, product=product
        )
        for listing, product in page_rows
    ]
    categories = sorted(
        {
            (product.category or "General").strip() or "General"
            for _listing, product in await ecom.published_listings(db, tenant.id)
        }
    )
    return env(
        {
            "storefront": {
                **{k: v for k, v in ecom.serialize_storefront(storefront_row, tenant).items() if k != "preview_token"},
                "preview": bool(_public_preview(request, preview_token)),
                "redirect_host": redirect_host,
                "https_ready": bool(domain.https_ready) if domain else False,
            },
            "catalog": items,
            "categories": categories,
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    )


@storefront.get("/media/{kind}")
async def public_media(
    kind: Literal["logo", "banner", "favicon"],
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, storefront_row, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    key = getattr(storefront_row, ecom.storefront_media_attr(kind))
    if not key:
        raise HTTPException(status_code=404, detail=f"No storefront {kind} uploaded")
    return logo_media_svc.keyed_media_response(
        key,
        tenant_id=tenant.id,
        request=request,
        cache_control="private, no-cache" if _public_preview(request, preview_token) else "public, max-age=300",
        vary="Host, X-Forwarded-Host, X-Storefront-Preview",
    )


@storefront.get("/products/{product_id}/image")
async def public_product_image(
    product_id: UuidIdValue,
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, _storefront, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    product = await db.get(m.Product, product_id)
    listing = await ecom.listing_for_product(db, tenant.id, product_id)
    if (
        product is None
        or product.tenant_id != tenant.id
        or not product.image_url
        or listing is None
        or not listing.is_published
    ):
        raise HTTPException(status_code=404, detail="Product image is not published")
    # Revalidate every time so unpublishing takes effect at once; 304 still skips the bytes.
    return logo_media_svc.keyed_media_response(
        product.image_url,
        tenant_id=tenant.id,
        request=request,
        cache_control="private, no-cache" if _public_preview(request, preview_token) else "public, no-cache",
        vary="Host, X-Forwarded-Host, X-Storefront-Preview",
    )


@storefront.post("/cart")
async def public_create_cart(
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, _storefront, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    cart = await ecom.create_cart(db, tenant.id)
    await db.commit()
    return env(await ecom.serialize_cart(db, cart))


@storefront.get("/cart/{token}")
async def public_get_cart(
    token: StorefrontSecretTokenValue,
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, _storefront, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    cart = await ecom.get_cart(db, tenant_id=tenant.id, token=token)
    return env(await ecom.serialize_cart(db, cart))


@storefront.post("/cart/{token}/items")
async def public_cart_item(
    token: StorefrontSecretTokenValue,
    payload: CartItemBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, storefront_row, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    cart = await ecom.get_cart(db, tenant_id=tenant.id, token=token)
    await ecom.set_cart_item(
        db,
        tenant=tenant,
        storefront=storefront_row,
        cart=cart,
        product_id=payload.product_id,
        quantity=payload.quantity,
        variant_id=payload.variant_id,
    )
    await db.commit()
    return env(await ecom.serialize_cart(db, cart))


@storefront.post("/checkout")
async def public_checkout(
    payload: CheckoutBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, storefront_row, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    cart = await ecom.get_cart(db, tenant_id=tenant.id, token=payload.cart_token)
    shopper = await ecom.get_shopper_by_session(
        db, tenant_id=tenant.id, token=_shopper_token(request)
    )
    order = await ecom.checkout(
        db,
        tenant=tenant,
        storefront=storefront_row,
        cart=cart,
        guest_name=payload.guest_name,
        guest_email=str(payload.guest_email) if payload.guest_email else None,
        guest_phone=payload.guest_phone,
        fulfillment=payload.fulfillment,
        delivery_address=payload.delivery_address,
        notes=payload.notes,
        shopper=shopper,
    )
    pay = await payments_svc.initialize_checkout(
        db, tenant=tenant, order=order, frontend_url=settings.FRONTEND_URL
    )
    await db.commit()
    items = await ecom.order_items(db, order.id)
    return env({**ecom.serialize_order(order, items), "payment": pay})


@storefront.post("/account/register")
async def public_register_shopper(
    payload: ShopperRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, _storefront, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    row = await ecom.register_shopper(
        db, tenant=tenant, name=payload.name, email=str(payload.email), password=payload.password
    )
    await db.commit()
    return env(ecom.serialize_shopper(row), "Storefront account created. This is not an ERP staff login.")


@storefront.post("/account/login")
async def public_login_shopper(
    payload: ShopperLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, _storefront, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    row = await ecom.login_shopper(db, tenant=tenant, email=str(payload.email), password=payload.password)
    await db.commit()
    return env(ecom.serialize_shopper(row))


@storefront.get("/account/me")
async def public_shopper_me(
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, _storefront, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    shopper = await ecom.get_shopper_by_session(db, tenant_id=tenant.id, token=_shopper_token(request))
    if shopper is None:
        raise HTTPException(status_code=401, detail="Sign in to the storefront")
    return env(ecom.serialize_shopper(shopper))


@storefront.post("/account/logout")
async def public_logout_shopper(
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, _storefront, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    shopper = await ecom.get_shopper_by_session(db, tenant_id=tenant.id, token=_shopper_token(request))
    if shopper is not None:
        await ecom.logout_shopper(db, shopper)
        await db.commit()
    return env({"logged_out": True})


@storefront.get("/account/orders")
async def public_shopper_orders(
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, _storefront, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    shopper = await ecom.get_shopper_by_session(db, tenant_id=tenant.id, token=_shopper_token(request))
    if shopper is None:
        raise HTTPException(status_code=401, detail="Sign in to the storefront to see order history")
    rows = await ecom.shopper_orders(db, shopper)
    return env({"shopper": ecom.serialize_shopper(shopper), "orders": [ecom.serialize_order(row) for row in rows]})


@storefront.get("/orders/{tracking_token}")
async def public_track_order(
    tracking_token: StorefrontSecretTokenValue,
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, _storefront, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    order = await ecom.get_order_by_tracking(db, tenant_id=tenant.id, tracking_token=tracking_token)
    items = await ecom.order_items(db, order.id)
    payload = ecom.serialize_order(order, items)
    for line, item in zip(payload.get("items") or [], items):
        product = await db.get(m.Product, item.product_id)
        variant = await db.get(m.ProductVariant, item.variant_id) if item.variant_id else None
        line["name"] = product.name if product else "Item"
        line["variant_name"] = variant.name if variant else None
        line["image_url"] = ecom.public_product_image_path(product.id) if product and product.image_url else None
    return env(payload)


@storefront.get("/orders/{tracking_token}/return")
async def public_payment_return(
    tracking_token: StorefrontSecretTokenValue,
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, _storefront, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    order = await ecom.get_order_by_tracking(db, tenant_id=tenant.id, tracking_token=tracking_token)
    return env(
        {
            **ecom.serialize_order(order),
            "return_marks_paid": False,
            "message": "This return page does not mark the order paid. Wait for the signed webhook or staff collection.",
        }
    )


@storefront.post("/payments/webhook/{provider}")
async def public_payment_webhook(
    provider: Literal["mock", "paystack", "flutterwave"],
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
    x_ribdigi_signature: Annotated[str | None, Header()] = None,
    x_paystack_signature: Annotated[str | None, Header()] = None,
):
    body = await request.body()
    signature = x_ribdigi_signature or x_paystack_signature
    result = await payments_svc.apply_signed_webhook(
        db,
        provider=provider,
        body=body,
        signature=signature,
        hostname=host,
        forwarded_host=x_forwarded_host,
        preview_token=_public_preview(request, preview_token),
    )
    await db.commit()
    return env(result)


@storefront.get("/policies/{slug}")
async def public_policy(
    slug: Literal["contact", "shipping", "returns", "privacy"],
    request: Request,
    db: AsyncSession = Depends(get_db),
    preview_token: Annotated[StorefrontSecretTokenValue | None, Query()] = None,
    host: Annotated[str | None, Header()] = None,
    x_forwarded_host: Annotated[str | None, Header()] = None,
):
    tenant, storefront_row, _domain = await ecom.resolve_public_tenant(
        db, host=host, forwarded_host=x_forwarded_host, preview_token=_public_preview(request, preview_token)
    )
    wanted = (slug or "").strip().lower()
    if wanted == "contact":
        contact = " ".join(
            part
            for part in (
                f"Email {storefront_row.support_email}." if storefront_row.support_email else None,
                f"Phone {storefront_row.support_phone}." if storefront_row.support_phone else None,
                storefront_row.announcement,
            )
            if part
        ) or f"Contact {tenant.company_name}."
        return env({"slug": "contact", "company_name": tenant.company_name, "body": contact})
    key = {
        "shipping": storefront_row.policy_shipping,
        "returns": storefront_row.policy_returns,
        "privacy": storefront_row.policy_privacy,
    }.get(wanted)
    if key is None and wanted not in {"shipping", "returns", "privacy"}:
        raise HTTPException(status_code=404, detail="Policy not found")
    return env({"slug": wanted, "company_name": tenant.company_name, "body": key or ""})
