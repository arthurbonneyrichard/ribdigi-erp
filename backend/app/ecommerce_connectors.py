"""Ecommerce website connectors. WooCommerce is implemented; others stay closed."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ecommerce as ecom
from app import models as m
from app.ecommerce_secrets import decrypt_ecommerce_secret, encrypt_ecommerce_secret
from app.honesty import money_json

MAX_ATTEMPTS = 5
RETRY_MINUTES = (5, 15, 60, 180, 720)


class ConnectorClient(Protocol):
    platform: str

    async def fetch_products(self) -> list[dict[str, Any]]:
        ...

    async def fetch_orders(self) -> list[dict[str, Any]]:
        ...


class UnimplementedConnector:
    def __init__(self, platform: str):
        self.platform = platform

    async def fetch_products(self) -> list[dict[str, Any]]:
        raise HTTPException(
            status_code=501,
            detail=f"{self.platform} is not implemented. Use WooCommerce or the built-in storefront.",
        )

    async def fetch_orders(self) -> list[dict[str, Any]]:
        raise HTTPException(
            status_code=501,
            detail=f"{self.platform} is not implemented. Use WooCommerce or the built-in storefront.",
        )


class WooCommerceConnector:
    platform = "woocommerce"

    def __init__(self, *, store_url: str, consumer_key: str, consumer_secret: str, http_get=None, http_put=None):
        self.store_url = store_url.rstrip("/")
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self._http_get = http_get
        self._http_put = http_put

    async def _get(self, path: str) -> list[dict[str, Any]]:
        url = f"{self.store_url}{path}"
        if self._http_get is not None:
            return await self._http_get(url, self.consumer_key, self.consumer_secret)
        import httpx

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                auth=(self.consumer_key, self.consumer_secret),
                headers={"Accept": "application/json"},
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=400, detail="WooCommerce request failed")
        data = response.json()
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="WooCommerce returned an unexpected payload")
        return data

    async def fetch_products(self) -> list[dict[str, Any]]:
        return await self._get("/wp-json/wc/v3/products?per_page=50")

    async def fetch_orders(self) -> list[dict[str, Any]]:
        return await self._get("/wp-json/wc/v3/orders?per_page=50")

    async def _put(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.store_url}{path}"
        if self._http_put is not None:
            return await self._http_put(url, self.consumer_key, self.consumer_secret, body)
        import httpx

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.put(
                url,
                auth=(self.consumer_key, self.consumer_secret),
                json=body,
                headers={"Accept": "application/json"},
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=400, detail="WooCommerce update failed")
        data = response.json()
        return data if isinstance(data, dict) else {}

    async def update_order(self, external_id: str, status: str) -> dict[str, Any]:
        return await self._put(f"/wp-json/wc/v3/orders/{external_id}", {"status": status})

    async def update_product_stock(self, external_id: str, quantity: float) -> dict[str, Any]:
        return await self._put(
            f"/wp-json/wc/v3/products/{external_id}",
            {"manage_stock": True, "stock_quantity": int(quantity)},
        )


_http_get_override = None
_http_put_override = None


def set_connector_http_get(fn) -> None:
    global _http_get_override
    _http_get_override = fn


def set_connector_http_put(fn) -> None:
    global _http_put_override
    _http_put_override = fn


def validate_store_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Store URL must be an absolute http(s) address")
    if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
        raise HTTPException(status_code=400, detail="Store URL must not include credentials")
    if parsed.scheme == "http" and parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "testserver",
        "host.docker.internal",
    }:
        raise HTTPException(status_code=400, detail="Remote store URLs must use https")
    return f"{parsed.scheme}://{parsed.netloc}"


def serialize_connector(row: m.EcommerceConnector) -> dict[str, Any]:
    return {
        "id": row.id,
        "platform": row.platform,
        "enabled": bool(row.is_enabled),
        "store_url": row.store_url,
        "credentials_configured": bool(row.credentials_enc),
        "implemented": row.platform in ecom.IMPLEMENTED_CONNECTORS,
        "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
        "last_error": row.last_error,
    }


async def list_connectors(db: AsyncSession, tenant_id: str) -> list[m.EcommerceConnector]:
    return list(
        (
            await db.execute(
                select(m.EcommerceConnector).where(m.EcommerceConnector.tenant_id == tenant_id)
            )
        ).scalars().all()
    )


async def upsert_connector(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    platform: str,
    store_url: str | None,
    consumer_key: str | None,
    consumer_secret: str | None,
    enabled: bool | None,
) -> m.EcommerceConnector:
    ecom.assert_ecommerce_entitled(tenant)
    name = (platform or "").strip().lower()
    if name not in ecom.IMPLEMENTED_CONNECTORS | ecom.UNIMPLEMENTED_CONNECTORS:
        raise HTTPException(status_code=400, detail="Unknown ecommerce platform")
    if name not in ecom.IMPLEMENTED_CONNECTORS:
        raise HTTPException(
            status_code=501,
            detail=f"{name} is not implemented. Use WooCommerce or the built-in storefront.",
        )
    row = (
        await db.execute(
            select(m.EcommerceConnector).where(
                m.EcommerceConnector.tenant_id == tenant.id,
                m.EcommerceConnector.platform == name,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = m.EcommerceConnector(tenant_id=tenant.id, platform=name)
        db.add(row)
    if store_url is not None:
        row.store_url = validate_store_url(store_url)
    if consumer_key or consumer_secret:
        existing = {}
        if row.credentials_enc:
            try:
                existing = json.loads(decrypt_ecommerce_secret(row.credentials_enc))
            except Exception:
                existing = {}
        blob = {
            "consumer_key": (consumer_key or existing.get("consumer_key") or "").strip(),
            "consumer_secret": (consumer_secret or existing.get("consumer_secret") or "").strip(),
        }
        if not blob["consumer_key"] or not blob["consumer_secret"]:
            raise HTTPException(status_code=400, detail="WooCommerce key and secret are required")
        row.credentials_enc = encrypt_ecommerce_secret(json.dumps(blob))
    if enabled is not None:
        row.is_enabled = bool(enabled)
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


def _client_for(row: m.EcommerceConnector) -> ConnectorClient:
    if row.platform != "woocommerce":
        return UnimplementedConnector(row.platform)
    if not row.store_url or not row.credentials_enc:
        raise HTTPException(status_code=400, detail="WooCommerce URL and credentials are required")
    creds = json.loads(decrypt_ecommerce_secret(row.credentials_enc))
    return WooCommerceConnector(
        store_url=row.store_url,
        consumer_key=str(creds.get("consumer_key") or ""),
        consumer_secret=str(creds.get("consumer_secret") or ""),
        http_get=_http_get_override,
        http_put=_http_put_override,
    )


async def _existing_product_by_sku(db: AsyncSession, tenant_id: str, sku: str) -> m.Product | None:
    return (
        await db.execute(
            select(m.Product).where(m.Product.tenant_id == tenant_id, m.Product.sku == sku)
        )
    ).scalar_one_or_none()


async def import_woocommerce_products(
    db: AsyncSession, *, tenant: m.Tenant, connector: m.EcommerceConnector
) -> dict[str, int]:
    client = _client_for(connector)
    created = 0
    linked = 0
    skipped = 0
    for raw in await client.fetch_products():
        external_id = str(raw.get("id") or "").strip()
        name = str(raw.get("name") or "").strip()
        sku = str(raw.get("sku") or f"WOO-{external_id}").strip().upper()[:100]
        if not external_id or not name:
            skipped += 1
            continue
        existing_listing = (
            await db.execute(
                select(m.EcommerceListing).where(
                    m.EcommerceListing.tenant_id == tenant.id,
                    m.EcommerceListing.external_id == f"woo:{external_id}",
                )
            )
        ).scalar_one_or_none()
        if existing_listing is not None:
            skipped += 1
            continue
        product = await _existing_product_by_sku(db, tenant.id, sku)
        if product is None:
            price = money_json(raw.get("price") or raw.get("regular_price") or 0)
            product = m.Product(
                tenant_id=tenant.id,
                name=name[:200],
                sku=sku,
                description=(str(raw.get("short_description") or "")[:500] or None),
                selling_price=price,
                cost_price=0,
                stock_qty=0,
                is_active=True,
            )
            db.add(product)
            await db.flush()
            created += 1
        await ecom.upsert_listing(
            db,
            tenant=tenant,
            product_id=product.id,
            is_published=False,
            online_price=money_json(raw.get("price") or raw.get("regular_price") or 0) or None,
            external_id=f"woo:{external_id}",
        )
        linked += 1
    await db.flush()
    return {"created": created, "linked": linked, "skipped": skipped}


async def import_woocommerce_orders(
    db: AsyncSession, *, tenant: m.Tenant, connector: m.EcommerceConnector
) -> dict[str, int]:
    client = _client_for(connector)
    imported = 0
    skipped = 0
    storefront = await ecom.require_storefront(db, tenant.id)
    for raw in await client.fetch_orders():
        external_id = f"woo:{raw.get('id')}"
        existing = (
            await db.execute(
                select(m.EcommerceOrder).where(
                    m.EcommerceOrder.tenant_id == tenant.id,
                    m.EcommerceOrder.external_id == external_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue
        billing = raw.get("billing") if isinstance(raw.get("billing"), dict) else {}
        name = " ".join(
            part for part in (billing.get("first_name"), billing.get("last_name")) if part
        ).strip() or "WooCommerce customer"
        order = m.EcommerceOrder(
            tenant_id=tenant.id,
            order_number=await ecom.next_order_number(db, tenant.id),
            tracking_token=ecom.new_secret_token(24),
            status="awaiting_payment",
            fulfillment="delivery",
            guest_name=name[:180],
            guest_email=(billing.get("email") or None),
            guest_phone=(billing.get("phone") or None),
            delivery_address=(billing.get("address_1") or None),
            currency=str(raw.get("currency") or tenant.currency or "GHS"),
            total_amount=money_json(raw.get("total") or 0),
            subtotal=money_json(raw.get("total") or 0),
            external_id=external_id,
            warehouse_id=storefront.fulfillment_warehouse_id,
        )
        db.add(order)
        await db.flush()
        for line in raw.get("line_items") or []:
            sku = str(line.get("sku") or "").strip().upper()
            product = await _existing_product_by_sku(db, tenant.id, sku) if sku else None
            if product is None:
                continue
            qty = money_json(line.get("quantity") or 0)
            price = money_json(line.get("price") or 0)
            db.add(
                m.EcommerceOrderItem(
                    tenant_id=tenant.id,
                    order_id=order.id,
                    product_id=product.id,
                    quantity=qty,
                    unit_price=price,
                    line_total=money_json(qty * price),
                )
            )
        imported += 1
    await db.flush()
    return {"imported": imported, "skipped": skipped}


def serialize_sync_job(row: m.EcommerceSyncJob) -> dict[str, Any]:
    return {
        "id": row.id,
        "connector_id": row.connector_id,
        "kind": row.kind,
        "status": row.status,
        "attempt": row.attempt,
        "stats": row.stats or {},
        "error": row.error,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


async def list_sync_jobs(db: AsyncSession, tenant_id: str) -> list[m.EcommerceSyncJob]:
    return list(
        (
            await db.execute(
                select(m.EcommerceSyncJob)
                .where(m.EcommerceSyncJob.tenant_id == tenant_id)
                .order_by(m.EcommerceSyncJob.created_at.desc())
            )
        ).scalars().all()
    )


async def run_connector_sync(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    connector: m.EcommerceConnector,
    kind: str,
) -> m.EcommerceSyncJob:
    ecom.assert_ecommerce_entitled(tenant)
    running = (
        await db.execute(
            select(m.EcommerceSyncJob).where(
                m.EcommerceSyncJob.tenant_id == tenant.id,
                m.EcommerceSyncJob.connector_id == connector.id,
                m.EcommerceSyncJob.kind == kind,
                m.EcommerceSyncJob.status == "running",
            )
        )
    ).scalar_one_or_none()
    if running is not None:
        return running
    job = m.EcommerceSyncJob(
        tenant_id=tenant.id,
        connector_id=connector.id,
        kind=kind,
        status="running",
        attempt=1,
        started_at=datetime.utcnow(),
    )
    db.add(job)
    await db.flush()
    try:
        if kind == "products":
            stats = await import_woocommerce_products(db, tenant=tenant, connector=connector)
        elif kind == "orders":
            stats = await import_woocommerce_orders(db, tenant=tenant, connector=connector)
        else:
            raise HTTPException(status_code=400, detail="Unknown sync kind")
        job.status = "succeeded"
        job.stats = stats
        job.finished_at = datetime.utcnow()
        connector.last_sync_at = job.finished_at
        connector.last_error = None
        connector.next_sync_at = datetime.utcnow() + timedelta(minutes=30)
    except HTTPException as exc:
        job.status = "failed"
        job.error = str(exc.detail)[:500]
        job.finished_at = datetime.utcnow()
        delay = RETRY_MINUTES[min(job.attempt - 1, len(RETRY_MINUTES) - 1)]
        job.next_retry_at = datetime.utcnow() + timedelta(minutes=delay)
        connector.last_error = job.error
        if exc.status_code == 501:
            raise
    await db.flush()
    return job


async def retry_failed_syncs(db: AsyncSession, tenant_id: str) -> int:
    now = datetime.utcnow()
    due = (
        await db.execute(
            select(m.EcommerceSyncJob).where(
                m.EcommerceSyncJob.tenant_id == tenant_id,
                m.EcommerceSyncJob.status == "failed",
                m.EcommerceSyncJob.attempt < MAX_ATTEMPTS,
                m.EcommerceSyncJob.next_retry_at.is_not(None),
                m.EcommerceSyncJob.next_retry_at <= now,
            )
        )
    ).scalars().all()
    retried = 0
    for job in due:
        connector = await db.get(m.EcommerceConnector, job.connector_id)
        tenant = await ecom.get_tenant(db, tenant_id)
        if connector is None or not connector.is_enabled:
            continue
        running = (
            await db.execute(
                select(m.EcommerceSyncJob).where(
                    m.EcommerceSyncJob.tenant_id == tenant_id,
                    m.EcommerceSyncJob.connector_id == connector.id,
                    m.EcommerceSyncJob.kind == job.kind,
                    m.EcommerceSyncJob.status == "running",
                )
            )
        ).scalar_one_or_none()
        if running is not None:
            continue
        job.status = "running"
        job.attempt += 1
        job.started_at = now
        job.error = None
        await db.flush()
        try:
            if job.kind == "products":
                stats = await import_woocommerce_products(db, tenant=tenant, connector=connector)
            else:
                stats = await import_woocommerce_orders(db, tenant=tenant, connector=connector)
            job.status = "succeeded"
            job.stats = stats
            job.finished_at = datetime.utcnow()
            connector.last_error = None
        except HTTPException as exc:
            job.status = "failed"
            job.error = str(exc.detail)[:500]
            job.finished_at = datetime.utcnow()
            delay = RETRY_MINUTES[min(job.attempt - 1, len(RETRY_MINUTES) - 1)]
            job.next_retry_at = datetime.utcnow() + timedelta(minutes=delay)
        retried += 1
    return retried


WOO_ORDER_STATUS = {
    "paid": "processing",
    "packed": "processing",
    "dispatched": "completed",
    "delivered": "completed",
    "fulfilled": "completed",
    "cancelled": "cancelled",
    "expired": "cancelled",
    "returned": "refunded",
}


async def push_order_and_stock(
    db: AsyncSession, *, tenant: m.Tenant, order: m.EcommerceOrder
) -> dict[str, Any]:
    """Best-effort Woo outbound. ERP posting already succeeded; failures stay on last_error."""
    result = {"pushed": False, "stock": 0}
    if not order.external_id or not str(order.external_id).startswith("woo:"):
        return result
    connector = (
        await db.execute(
            select(m.EcommerceConnector).where(
                m.EcommerceConnector.tenant_id == tenant.id,
                m.EcommerceConnector.platform == "woocommerce",
                m.EcommerceConnector.is_enabled.is_(True),
            )
        )
    ).scalar_one_or_none()
    if connector is None or not connector.credentials_enc:
        return result
    try:
        client = _client_for(connector)
        woo_id = str(order.external_id).split(":", 1)[1]
        status = WOO_ORDER_STATUS.get(order.status)
        if status:
            await client.update_order(woo_id, status)
            result["pushed"] = True
        storefront = await ecom.require_storefront(db, tenant.id)
        items = await ecom.order_items(db, order.id)
        for item in items:
            listing = await ecom.listing_for_product(db, tenant.id, item.product_id)
            if listing is None or not listing.external_id or not listing.external_id.startswith("woo:"):
                continue
            warehouse = await ecom.fulfillment_warehouse(db, tenant_id=tenant.id, storefront=storefront, listing=listing)
            qty = await ecom.online_available(
                db,
                tenant_id=tenant.id,
                warehouse_id=warehouse.id,
                product_id=item.product_id,
                stock_buffer=float(listing.stock_buffer or 0),
            )
            await client.update_product_stock(listing.external_id.split(":", 1)[1], qty)
            result["stock"] += 1
        connector.last_error = None
    except Exception as exc:
        connector.last_error = str(getattr(exc, "detail", exc))[:500]
        result["error"] = connector.last_error
    await db.flush()
    return result
