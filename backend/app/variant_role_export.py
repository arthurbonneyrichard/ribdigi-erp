"""CSV export for product variants and custom roles (Stage 124 X1);
per-product variants path export (Stage 156 V1)."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import catalog as catalog_svc

VARIANT_EXPORT_COLUMNS = [
    "product_id",
    "product_sku",
    "product_name",
    "name",
    "sku",
    "barcode",
    "size",
    "color",
    "flavor",
    "cost_price",
    "selling_price",
    "stock_qty",
    "is_active",
]

ROLE_EXPORT_COLUMNS = [
    "slug",
    "label",
    "description",
    "record_scope",
    "is_active",
]

PERMISSIONS_MATRIX_EXPORT_COLUMNS = [
    "role",
    "label",
    "system",
    "record_scope",
    "is_active",
    "module",
    "action",
    "granted",
]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))
    return str(value)


def _apply_active_filter(stmt, column, *, is_active: bool | None, active_only: bool):
    if is_active is not None:
        return stmt.where(column.is_(bool(is_active)))
    if active_only:
        return stmt.where(column.is_(True))
    return stmt


async def export_variants_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str | None = None,
    is_active: bool | None = None,
    active_only: bool = False,
) -> str:
    stmt = (
        select(m.ProductVariant, m.Product)
        .join(m.Product, m.Product.id == m.ProductVariant.product_id)
        .where(m.ProductVariant.tenant_id == tenant_id, m.Product.tenant_id == tenant_id)
    )
    if product_id:
        stmt = stmt.where(m.ProductVariant.product_id == product_id)
    stmt = _apply_active_filter(
        stmt, m.ProductVariant.is_active, is_active=is_active, active_only=active_only
    )
    rows = (
        await db.execute(stmt.order_by(m.Product.sku, m.ProductVariant.sku))
    ).all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=VARIANT_EXPORT_COLUMNS)
    writer.writeheader()
    for variant, product in rows:
        writer.writerow(
            {
                "product_id": _cell(variant.product_id),
                "product_sku": _cell(product.sku),
                "product_name": _cell(product.name),
                "name": _cell(variant.name),
                "sku": _cell(variant.sku),
                "barcode": _cell(variant.barcode),
                "size": _cell(variant.size),
                "color": _cell(variant.color),
                "flavor": _cell(variant.flavor),
                "cost_price": _cell(float(variant.cost_price or 0)),
                "selling_price": _cell(float(variant.selling_price or 0)),
                "stock_qty": _cell(float(variant.stock_qty or 0)),
                "is_active": _cell(bool(variant.is_active)),
            }
        )
    return buf.getvalue()


async def export_product_variants_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
) -> str:
    """Stage 156 V1 — path-scoped per-product variants CSV (distinct from Stage 124 roster)."""
    await catalog_svc.get_product(db, tenant_id, product_id)
    return await export_variants_csv(
        db,
        tenant_id=tenant_id,
        product_id=product_id,
        is_active=is_active,
        active_only=active_only,
    )


async def export_custom_roles_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
) -> str:
    stmt = select(m.CustomRole).where(m.CustomRole.tenant_id == tenant_id)
    stmt = _apply_active_filter(
        stmt, m.CustomRole.is_active, is_active=is_active, active_only=active_only
    )
    rows = (await db.execute(stmt.order_by(m.CustomRole.slug))).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=ROLE_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "slug": _cell(row.slug),
                "label": _cell(row.label),
                "description": _cell(row.description),
                "record_scope": _cell(row.record_scope or "own"),
                "is_active": _cell(bool(row.is_active)),
            }
        )
    return buf.getvalue()


async def export_permissions_matrix_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
) -> str:
    """Stage 152 M1 — role×module×action permissions matrix CSV (system + custom)."""
    from app import roles as roles_svc

    catalog = await roles_svc.list_role_catalog(
        db, tenant_id, active_only=active_only, is_active=is_active
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PERMISSIONS_MATRIX_EXPORT_COLUMNS)
    writer.writeheader()
    for row in catalog:
        role = row.get("role") or row.get("slug") or ""
        label = row.get("label") or role
        system = bool(row.get("system"))
        record_scope = row.get("record_scope") or "own"
        active = row.get("is_active")
        if active is None:
            active = True
        perms = row.get("permissions") if isinstance(row.get("permissions"), dict) else {}
        # Drop record_scope key if present inside permissions map
        modules = {k: v for k, v in perms.items() if k != "record_scope"}
        if not modules:
            writer.writerow(
                {
                    "role": _cell(role),
                    "label": _cell(label),
                    "system": _cell(system),
                    "record_scope": _cell(record_scope),
                    "is_active": _cell(bool(active)),
                    "module": "",
                    "action": "",
                    "granted": "false",
                }
            )
            continue
        if modules.get("*") == ["*"] or (isinstance(modules.get("*"), list) and "*" in modules["*"]):
            writer.writerow(
                {
                    "role": _cell(role),
                    "label": _cell(label),
                    "system": _cell(system),
                    "record_scope": _cell(record_scope),
                    "is_active": _cell(bool(active)),
                    "module": "*",
                    "action": "*",
                    "granted": "true",
                }
            )
            continue
        for module, actions in sorted(modules.items(), key=lambda kv: kv[0]):
            action_list = actions if isinstance(actions, list) else [actions]
            for action in action_list:
                writer.writerow(
                    {
                        "role": _cell(role),
                        "label": _cell(label),
                        "system": _cell(system),
                        "record_scope": _cell(record_scope),
                        "is_active": _cell(bool(active)),
                        "module": _cell(module),
                        "action": _cell(action),
                        "granted": "true",
                    }
                )
    return buf.getvalue()
