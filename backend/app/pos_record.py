"""POS sale recording extracted for Stage 164 sync + online reuse."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import pos as pos_svc
from app import stores as stores_svc
from app import customers as customers_svc
from app import cache as cache_svc
from app.inventory import assert_outbound_lines_stock_available, apply_line_items_stock
from app.schemas import PosSaleCreate


async def find_sale_by_client_request_id(
    db: AsyncSession,
    tenant_id: str,
    client_request_id: str,
    *,
    company_id: str | None = None,
) -> m.Transaction | None:
    key = (client_request_id or "").strip()
    if not key:
        return None
    stmt = select(m.Transaction).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.client_request_id == key,
        m.Transaction.tx_type == "pos_sale",
    )
    if company_id:
        stmt = stmt.where(m.Transaction.company_id == company_id)
    return (await db.execute(stmt)).scalar_one_or_none()


def serialize_sale_result(tx: m.Transaction) -> dict[str, Any]:
    payload = tx.payload or {}
    return {
        "id": tx.id,
        "reference": tx.reference,
        "session_id": tx.session_id,
        "party_id": tx.party_id,
        "client_request_id": tx.client_request_id,
        "subtotal": float(tx.subtotal or 0),
        "tax": float(tx.tax or 0),
        "discount_amount": float(payload.get("discount_amount") or 0),
        "total": float(tx.total or 0),
        "payment_method": payload.get("payment_method") or "cash",
        "payments": payload.get("payments") or [],
        "credit_limit_overridden": bool(payload.get("credit_limit_overridden")),
        "credit_override_reason": payload.get("credit_override_reason"),
        "replayed": True,
    }


async def record_pos_sale(
    db: AsyncSession,
    *,
    claims: dict,
    payload: PosSaleCreate,
    commit: bool = True,
) -> dict[str, Any]:
    """Record a POS sale. When client_request_id is set, replays are idempotent."""
    client_request_id = (getattr(payload, "client_request_id", None) or "").strip() or None
    if client_request_id:
        if len(client_request_id) < 8:
            raise HTTPException(status_code=400, detail="client_request_id must be at least 8 characters")
        if len(client_request_id) > 80:
            raise HTTPException(status_code=400, detail="client_request_id must be at most 80 characters")

    session = await pos_svc.require_open_session(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        session_id=payload.session_id,
        company_id=claims.get("company_id"),
    )
    company_id = claims.get("company_id") or getattr(session, "company_id", None)
    if client_request_id:
        existing = await find_sale_by_client_request_id(
            db,
            claims["tenant_id"],
            client_request_id,
            company_id=company_id,
        )
        if existing:
            return serialize_sale_result(existing)
    items = [i.model_dump() for i in payload.items]
    from app.tax import resolve_product_tax
    from app.catalog import resolve_sale_line

    group_discount = await customers_svc.customer_group_discount_percent(
        db, claims["tenant_id"], payload.party_id
    )
    subtotal = 0.0
    tax_total = 0.0
    line_discounts = 0.0
    priced_items = []
    for item in items:
        product, variant, unit_price = await resolve_sale_line(
            db,
            claims["tenant_id"],
            item,
            group_discount_percent=group_discount,
        )
        spec = await resolve_product_tax(db, claims["tenant_id"], product)
        line_discount = round(float(item.get("discount") or 0), 2)
        if line_discount < 0:
            raise HTTPException(status_code=400, detail="Line discount must be >= 0")
        gross_before_discount = round(float(item["quantity"]) * float(unit_price), 2)
        if line_discount > gross_before_discount:
            raise HTTPException(status_code=400, detail="Line discount exceeds line amount")
        taxable_base = round(gross_before_discount - line_discount, 2)
        line_sub, line_tax, line_gross = spec.compute_amounts(taxable_base)
        subtotal += line_sub
        line_discounts += line_discount
        if not spec.is_reverse_charge:
            tax_total += line_tax
        priced_items.append(
            {
                **item,
                "variant_id": variant.id if variant else item.get("variant_id"),
                "name": variant.name if variant else product.name,
                "sku": variant.sku if variant else product.sku,
                "unit_price": unit_price,
                "discount": line_discount,
                "tax_rate": spec.rate_pct,
                "supply_category": spec.supply_category,
                "line_subtotal": line_sub,
                "line_tax": 0.0 if spec.is_reverse_charge else line_tax,
                "line_total": line_gross,
                "is_reverse_charge": spec.is_reverse_charge,
            }
        )
    cart_discount = round(float(payload.discount_amount or 0), 2)
    if cart_discount < 0:
        raise HTTPException(status_code=400, detail="discount_amount must be >= 0")
    max_cart_discount = round(subtotal + tax_total, 2)
    if cart_discount > max_cart_discount:
        raise HTTPException(status_code=400, detail="Cart discount exceeds sale total")
    total = round(subtotal + tax_total - cart_discount, 2)

    payments = pos_svc.resolve_sale_payments(
        total=total,
        payment_method=payload.payment_method,
        payments=[p.model_dump() for p in payload.payments] if payload.payments else None,
    )
    payment_method = pos_svc.primary_payment_method(payments)
    credit_amount = pos_svc.credit_portion(payments)
    if credit_amount > 0 and not payload.party_id:
        raise HTTPException(status_code=400, detail="Credit sales require a registered customer")

    party = None
    credit_gate = None
    if payload.party_id:
        party = (
            await db.execute(
                select(m.Party).where(
                    m.Party.id == payload.party_id,
                    m.Party.tenant_id == claims["tenant_id"],
                    m.Party.kind == "customer",
                )
            )
        ).scalar_one_or_none()
        if party is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        company_id = claims.get("company_id")
        if company_id and party.company_id and party.company_id != company_id:
            raise HTTPException(status_code=404, detail="Customer not found")
        if (party.status or "active") != "active":
            raise HTTPException(status_code=409, detail="Customer is not active")
        if credit_amount > 0:
            ctype = (party.party_type or "registered").strip().lower()
            if ctype == "walk-in":
                raise HTTPException(
                    status_code=400,
                    detail="Credit sales require a registered customer",
                )
            from app.credit import enforce_credit_limit

            perms = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
            credit_gate = await enforce_credit_limit(
                db,
                tenant_id=claims["tenant_id"],
                user_id=claims.get("sub"),
                role=claims.get("role") or "",
                permissions=perms,
                customer=party,
                additional_amount=credit_amount,
                override=bool(payload.credit_limit_override),
                override_reason=payload.credit_override_reason,
                entity="pos_sale",
                entity_id=None,
                module="pos",
                record_audit=False,
            )

    # Stage 13 H1 — fail-fast before Transaction / payments / journal are created.
    await assert_outbound_lines_stock_available(
        db,
        tenant_id=claims["tenant_id"],
        items=items,
    )

    ref = f"POS_SALE-{datetime.utcnow():%Y%m%d%H%M%S%f}"
    body = payload.model_dump()
    body.pop("items", None)
    body.pop("session_id", None)
    body.pop("payment_method", None)
    body.pop("payments", None)
    body.pop("credit_limit_override", None)
    body.pop("credit_override_reason", None)
    body["payload"] = {
        **(body.get("payload") or {}),
        "items": priced_items,
        "payment_method": payment_method,
        "payments": payments,
        "session_id": session.id,
        "discount_amount": cart_discount,
        "line_discounts": round(line_discounts, 2),
        "party_id": payload.party_id,
        "customer_name": party.name if party else None,
        "credit_limit_overridden": bool(credit_gate and credit_gate.get("overridden")),
        "credit_override_reason": (credit_gate or {}).get("override_reason"),
    }
    tx = m.Transaction(
        tenant_id=claims["tenant_id"],
        company_id=claims.get("company_id") or session.company_id,
        tx_type="pos_sale",
        reference=ref,
        client_request_id=client_request_id,
        party_id=payload.party_id,
        session_id=session.id,
        subtotal=round(subtotal, 2),
        tax=round(tax_total, 2),
        total=total,
        status=payload.status,
        payload=body["payload"],
    )
    db.add(tx)
    await db.flush()
    if credit_gate and credit_gate.get("overridden"):
        # Re-emit audit with sale id now that the transaction exists.
        from app import audit as audit_svc

        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims.get("sub"),
            action="credit_limit_override",
            entity="pos_sale",
            entity_id=tx.id,
            module="pos",
            details={
                "customer_id": party.id if party else None,
                "customer_name": party.name if party else None,
                "reason": credit_gate.get("override_reason"),
                "credit_limit": credit_gate.get("credit_limit"),
                "current_balance": credit_gate.get("current_balance"),
                "additional_amount": credit_gate.get("additional_amount"),
                "projected_balance": credit_gate.get("projected_balance"),
                "reference": ref,
            },
        )
    payment_rows = await pos_svc.record_pos_payments(
        db,
        tenant_id=claims["tenant_id"],
        sale_id=tx.id,
        payments=payments,
        company_id=tx.company_id,
    )

    warehouse_id = None
    if session.store_id:
        wh = await stores_svc.warehouse_for_store(db, claims["tenant_id"], session.store_id)
        warehouse_id = wh.id

    await apply_line_items_stock(
        db,
        tenant_id=claims["tenant_id"],
        items=items,
        movement_type="stock_out",
        user_id=claims["sub"],
        reference_type="pos_sale",
        reference_id=tx.id,
        outbound=True,
        warehouse_id=warehouse_id,
    )
    await pos_svc.apply_sale_to_session(
        session, total=total, payment_method=payment_method, payments=payments
    )

    if payload.party_id and credit_amount > 0:
        party = await db.get(m.Party, payload.party_id)
        if party and party.tenant_id == claims["tenant_id"]:
            party.balance = float(party.balance or 0) + float(credit_amount)

    from app.accounting import post_pos_sale_journal

    await post_pos_sale_journal(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims["sub"],
        tx=tx,
        payment_method=payment_method,
        payments=payments,
        company_id=tx.company_id,
    )

    from app import audit as audit_svc

    await audit_svc.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        action="pos_sale_completed",
        entity="pos_sale",
        entity_id=tx.id,
        details={
            "reference": ref,
            "session_id": session.id,
            "total": float(tx.total or 0),
            "tax": float(tx.tax or 0),
            "discount_amount": cart_discount,
            "payment_method": payment_method,
            "party_id": payload.party_id,
            "sale_count_after": int(session.sale_count or 0),
        },
        module="pos",
    )

    from app import cash_drawer as cash_drawer_svc

    drawer = await cash_drawer_svc.maybe_open_on_cash_sale(
        db,
        tenant_id=claims["tenant_id"],
        store_id=session.store_id,
        payment_method="cash" if pos_svc.has_cash_tender(payments) else payment_method,
        sale_id=tx.id,
        user_id=claims.get("sub"),
    )
    payload_out = {
        "id": tx.id,
        "reference": ref,
        "session_id": session.id,
        "party_id": payload.party_id,
        "subtotal": float(tx.subtotal),
        "tax": float(tx.tax),
        "discount_amount": cart_discount,
        "total": float(tx.total),
        "payment_method": payment_method,
        "payments": [pos_svc.serialize_payment(p) for p in payment_rows],
        "credit_limit_overridden": bool(credit_gate and credit_gate.get("overridden")),
        "credit_override_reason": (credit_gate or {}).get("override_reason"),
    }
    if drawer is not None:
        payload_out["drawer"] = drawer
    payload_out["client_request_id"] = client_request_id
    payload_out["replayed"] = False
    if commit:
        await db.commit()
        await cache_svc.app_cache.invalidate_tenant(claims["tenant_id"])
    else:
        await db.flush()
    return payload_out

