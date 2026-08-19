"""Rule-based AI ERP chat assistant (Phase 4 / BR-21.1).

Answers natural-language questions from tenant data and can create a draft PO
when the user has purchasing write permission. No external LLM required.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.rbac import has_permission
from app.reports import apply_company_filter

POSTED_INVOICE_STATUSES = frozenset({"posted", "sent", "partial", "paid", "overdue"})

HELP_TEXT = (
    "I can answer questions about top products, sales this month, low stock, "
    "expenses, customers, and stockout predictions. "
    "I can also create a draft purchase order, e.g. "
    "'Create a purchase order for 50 units of Alpha Widget'."
)


def _can(claims: dict, module: str, action: str = "read") -> bool:
    role = claims.get("role") or ""
    overrides = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
    return has_permission(role, module, action, overrides=overrides)


def detect_intent(message: str) -> str:
    text = (message or "").strip().lower()
    if not text:
        return "empty"
    if re.search(r"\b(help|what can you|capabilities)\b", text):
        return "help"
    if re.search(r"\b(create|make|raise|generate)\b.*\b(purchase order|po)\b", text) or re.search(
        r"\border\b.*\b(units?|pcs|pieces)\b", text
    ):
        return "create_po"
    if re.search(r"\b(top|best)\b.*\b(product|seller|selling)\b", text) or "top selling" in text:
        return "top_product"
    if re.search(r"\b(sales|revenue)\b.*\b(month|this month|monthly)\b", text) or text in {
        "sales this month",
        "monthly sales",
    }:
        return "sales_month"
    if re.search(r"\blow stock\b|\breorder\b|\bout of stock\b", text):
        return "low_stock"
    if re.search(r"\b(stockout|stock out|predict|prediction|velocity)\b", text):
        return "stockout_prediction"
    if re.search(r"\b(expense|expenses|spending)\b", text):
        return "expenses"
    if re.search(r"\b(customer|customers)\b", text):
        return "customers"
    if re.search(r"\b(insight|insights|anomaly|anomalies)\b", text):
        return "insights"
    return "unknown"


def _parse_po_request(message: str) -> tuple[float | None, str | None]:
    """Extract qty and product name/sku fragment from a create-PO utterance."""
    text = message.strip()
    qty = None
    m_qty = re.search(
        r"(?:for\s+)?(\d+(?:\.\d+)?)\s*(?:units?|pcs|pieces)?\s+(?:of\s+)?(.+)$",
        text,
        re.I,
    )
    if m_qty:
        qty = float(m_qty.group(1))
        name = m_qty.group(2).strip(" .")
        name = re.sub(r"^(units?|pcs|pieces)\s+of\s+", "", name, flags=re.I)
        return qty, name or None
    m_alt = re.search(r"(\d+(?:\.\d+)?)\s+(.+)", text)
    if m_alt:
        return float(m_alt.group(1)), m_alt.group(2).strip(" .") or None
    return None, None


async def _top_product(
    db: AsyncSession, tenant_id: str, company_id: str | None = None
) -> dict:
    month_ago = datetime.utcnow() - timedelta(days=30)
    stmt = (
        select(
            m.Product.id,
            m.Product.name,
            m.Product.sku,
            func.coalesce(func.sum(m.SalesInvoiceItem.quantity), 0).label("qty"),
            func.coalesce(func.sum(m.SalesInvoiceItem.line_total), 0).label("revenue"),
        )
        .join(m.SalesInvoiceItem, m.SalesInvoiceItem.product_id == m.Product.id)
        .join(m.SalesInvoice, m.SalesInvoice.id == m.SalesInvoiceItem.sales_invoice_id)
        .where(
            m.Product.tenant_id == tenant_id,
            m.SalesInvoice.tenant_id == tenant_id,
            m.SalesInvoice.status.in_(list(POSTED_INVOICE_STATUSES)),
            m.SalesInvoice.created_at >= month_ago,
        )
        .group_by(m.Product.id, m.Product.name, m.Product.sku)
        .order_by(func.coalesce(func.sum(m.SalesInvoiceItem.line_total), 0).desc())
        .limit(1)
    )
    stmt = apply_company_filter(stmt, m.Product.company_id, company_id)
    stmt = apply_company_filter(stmt, m.SalesInvoice.company_id, company_id)
    row = (await db.execute(stmt)).first()
    if not row:
        return {
            "answer": "No posted sales in the last 30 days, so I cannot rank a top product yet.",
            "data": {},
        }
    return {
        "answer": (
            f"Your top selling product this month is {row.name} ({row.sku}) "
            f"with {float(row.qty):.0f} units and revenue {float(row.revenue):.2f}."
        ),
        "data": {
            "product_id": row.id,
            "name": row.name,
            "sku": row.sku,
            "quantity": float(row.qty),
            "revenue": float(row.revenue),
        },
    }


async def _sales_month(
    db: AsyncSession, tenant_id: str, company_id: str | None = None
) -> dict:
    month_ago = datetime.utcnow() - timedelta(days=30)
    total_stmt = select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(list(POSTED_INVOICE_STATUSES)),
        m.SalesInvoice.created_at >= month_ago,
    )
    total_stmt = apply_company_filter(total_stmt, m.SalesInvoice.company_id, company_id)
    total = float((await db.execute(total_stmt)).scalar_one() or 0)
    count_stmt = (
        select(func.count())
        .select_from(m.SalesInvoice)
        .where(
            m.SalesInvoice.tenant_id == tenant_id,
            m.SalesInvoice.status.in_(list(POSTED_INVOICE_STATUSES)),
            m.SalesInvoice.created_at >= month_ago,
        )
    )
    count_stmt = apply_company_filter(count_stmt, m.SalesInvoice.company_id, company_id)
    count = int((await db.execute(count_stmt)).scalar_one() or 0)
    return {
        "answer": f"Sales in the last 30 days: {total:.2f} across {count} posted invoice(s).",
        "data": {"total": total, "invoice_count": count},
    }


async def _low_stock(
    db: AsyncSession, tenant_id: str, company_id: str | None = None
) -> dict:
    stmt = (
        select(m.Product)
        .where(
            m.Product.tenant_id == tenant_id,
            m.Product.is_active == True,  # noqa: E712
            m.Product.stock_qty <= m.Product.reorder_level,
        )
        .order_by(m.Product.stock_qty.asc())
        .limit(10)
    )
    stmt = apply_company_filter(stmt, m.Product.company_id, company_id)
    rows = (await db.execute(stmt)).scalars().all()
    if not rows:
        return {"answer": "No products are currently at or below reorder level.", "data": {"items": []}}
    lines = [f"- {p.name} ({p.sku}): stock {float(p.stock_qty)}, reorder {float(p.reorder_level)}" for p in rows]
    return {
        "answer": f"{len(rows)} product(s) at/below reorder level:\n" + "\n".join(lines),
        "data": {
            "items": [
                {
                    "id": p.id,
                    "name": p.name,
                    "sku": p.sku,
                    "stock_qty": float(p.stock_qty),
                    "reorder_level": float(p.reorder_level),
                }
                for p in rows
            ]
        },
    }


async def _expenses(
    db: AsyncSession, tenant_id: str, company_id: str | None = None
) -> dict:
    month_ago = datetime.utcnow() - timedelta(days=30)
    stmt = select(func.coalesce(func.sum(m.Expense.amount), 0)).where(
        m.Expense.tenant_id == tenant_id,
        m.Expense.status == "approved",
        m.Expense.expense_date >= month_ago,
    )
    stmt = apply_company_filter(stmt, m.Expense.company_id, company_id)
    total = float((await db.execute(stmt)).scalar_one() or 0)
    return {
        "answer": f"Approved expenses in the last 30 days total {total:.2f}.",
        "data": {"total": total},
    }


async def _customers(
    db: AsyncSession, tenant_id: str, company_id: str | None = None
) -> dict:
    stmt = (
        select(func.count())
        .select_from(m.Party)
        .where(
            m.Party.tenant_id == tenant_id,
            m.Party.kind == "customer",
        )
    )
    stmt = apply_company_filter(stmt, m.Party.company_id, company_id)
    count = int((await db.execute(stmt)).scalar_one() or 0)
    return {"answer": f"You have {count} customer(s) on file.", "data": {"count": count}}


async def _create_po(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    claims: dict,
    message: str,
    company_id: str | None = None,
) -> dict:
    if not _can(claims, "purchasing", "write"):
        return {
            "answer": "Creating a purchase order requires purchasing write permission for your role.",
            "data": {"denied": True},
        }
    qty, name_frag = _parse_po_request(message)
    if not qty or qty <= 0 or not name_frag:
        return {
            "answer": (
                "Tell me the quantity and product, e.g. "
                "'Create a purchase order for 50 units of Alpha Widget'."
            ),
            "data": {},
        }
    frag = name_frag.strip()
    product_stmt = (
        select(m.Product)
        .where(
            m.Product.tenant_id == tenant_id,
            m.Product.is_active == True,  # noqa: E712
            (m.Product.name.ilike(f"%{frag}%")) | (m.Product.sku.ilike(f"%{frag}%")),
        )
        .limit(5)
    )
    product_stmt = apply_company_filter(product_stmt, m.Product.company_id, company_id)
    product = (await db.execute(product_stmt)).scalars().all()
    if not product:
        return {
            "answer": f"I could not find an active product matching '{frag}'.",
            "data": {},
        }
    if len(product) > 1:
        opts = ", ".join(f"{p.name} ({p.sku})" for p in product)
        return {
            "answer": f"Multiple products match '{frag}': {opts}. Please be more specific.",
            "data": {"candidates": [{"id": p.id, "name": p.name, "sku": p.sku} for p in product]},
        }
    prod = product[0]
    supplier_stmt = (
        select(m.Party)
        .where(
            m.Party.tenant_id == tenant_id,
            m.Party.kind == "supplier",
            m.Party.status == "active",
        )
        .order_by(m.Party.name)
        .limit(1)
    )
    supplier_stmt = apply_company_filter(supplier_stmt, m.Party.company_id, company_id)
    supplier = (await db.execute(supplier_stmt)).scalar_one_or_none()
    if not supplier:
        # fallback without status filter
        fallback_stmt = (
            select(m.Party)
            .where(m.Party.tenant_id == tenant_id, m.Party.kind == "supplier")
            .order_by(m.Party.name)
            .limit(1)
        )
        fallback_stmt = apply_company_filter(fallback_stmt, m.Party.company_id, company_id)
        supplier = (await db.execute(fallback_stmt)).scalar_one_or_none()
    if not supplier:
        return {
            "answer": "No supplier is set up yet. Add a supplier first, then ask me again.",
            "data": {},
        }

    from app import purchasing as purchasing_svc

    po = await purchasing_svc.create_purchase_order(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        supplier_id=supplier.id,
        items=[
            {
                "product_id": prod.id,
                "quantity": qty,
                "unit_price": float(prod.cost_price or 0),
            }
        ],
        notes=f"Created via AI chat: {message[:200]}",
        company_id=company_id if company_id is not None else claims.get("company_id"),
    )
    return {
        "answer": (
            f"Created draft purchase order {po.po_number} for {qty:g} × {prod.name} "
            f"({prod.sku}) from supplier {supplier.name}. Open Purchasing to review and send."
        ),
        "data": {
            "purchase_order_id": po.id,
            "po_number": po.po_number,
            "product_id": prod.id,
            "quantity": qty,
            "supplier_id": supplier.id,
        },
    }


async def handle_chat(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    claims: dict,
    message: str,
    company_id: str | None = None,
) -> dict:
    company_id = company_id if company_id is not None else claims.get("company_id")
    msg = (message or "").strip()
    intent = detect_intent(msg)
    data: dict = {}
    answer = HELP_TEXT

    if intent == "empty":
        answer = "Ask a question about your ERP data, or say 'help'."
    elif intent == "help":
        answer = HELP_TEXT
    elif intent == "top_product":
        if not _can(claims, "sales", "read") and not _can(claims, "dashboard", "read"):
            answer = "You do not have permission to view sales data."
        else:
            out = await _top_product(db, tenant_id, company_id=company_id)
            answer, data = out["answer"], out["data"]
    elif intent == "sales_month":
        if not _can(claims, "sales", "read") and not _can(claims, "dashboard", "read"):
            answer = "You do not have permission to view sales data."
        else:
            out = await _sales_month(db, tenant_id, company_id=company_id)
            answer, data = out["answer"], out["data"]
    elif intent == "low_stock":
        if not _can(claims, "inventory", "read"):
            answer = "You do not have permission to view inventory."
        else:
            out = await _low_stock(db, tenant_id, company_id=company_id)
            answer, data = out["answer"], out["data"]
    elif intent == "stockout_prediction":
        if not _can(claims, "ai", "read"):
            answer = "You do not have permission to view AI predictions."
        else:
            from app import ai_inventory as ai_inventory_svc

            pred = await ai_inventory_svc.predict_low_stock(
                db,
                tenant_id,
                at_risk_only=True,
                horizon_days=14,
                company_id=company_id,
            )
            if not pred["at_risk_count"]:
                answer = "No products are predicted to stock out within 14 days."
            else:
                lines = [
                    f"- {p['name']} (~{p['days_to_stockout']}d, suggest {p['suggested_order_qty']})"
                    for p in pred["predictions"][:5]
                ]
                answer = f"{pred['at_risk_count']} product(s) at risk:\n" + "\n".join(lines)
            data = {"at_risk_count": pred["at_risk_count"], "predictions": pred["predictions"][:5]}
    elif intent == "expenses":
        if not _can(claims, "expenses", "read") and not _can(claims, "dashboard", "read"):
            answer = "You do not have permission to view expenses."
        else:
            out = await _expenses(db, tenant_id, company_id=company_id)
            answer, data = out["answer"], out["data"]
    elif intent == "customers":
        if not _can(claims, "sales", "read") and not _can(claims, "credit", "read") and not _can(
            claims, "dashboard", "read"
        ):
            answer = "You do not have permission to view customers."
        else:
            out = await _customers(db, tenant_id, company_id=company_id)
            answer, data = out["answer"], out["data"]
    elif intent == "insights":
        if not _can(claims, "ai", "read"):
            answer = "You do not have permission to view AI insights."
        else:
            from app import ai_insights as ai_insights_svc

            insights = await ai_insights_svc.generate_insights(
                db, tenant_id, company_id=company_id
            )
            cards = insights["insights"][:5]
            if not cards:
                answer = insights["summaries"][0]
            else:
                answer = "Top insights:\n" + "\n".join(
                    f"- [{c['severity']}] {c['title']}: {c['summary']}" for c in cards
                )
            data = {"cards": cards}
    elif intent == "create_po":
        out = await _create_po(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            claims=claims,
            message=msg,
            company_id=company_id,
        )
        answer, data = out["answer"], out["data"]
    else:
        answer = (
            "I am not sure how to answer that yet. " + HELP_TEXT
        )

    row = m.AiQuery(
        tenant_id=tenant_id,
        company_id=company_id,
        user_id=user_id,
        role=claims.get("role"),
        message=msg,
        answer=answer,
        intent=intent,
        payload=data or None,
    )
    db.add(row)
    await db.flush()
    return {
        "id": row.id,
        "company_id": company_id,
        "intent": intent,
        "answer": answer,
        "reply": answer,
        "data": data,
        "created_at": row.created_at,
        "method": "rules_v1",
    }


async def list_history(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    limit: int = 50,
    company_id: str | None = None,
) -> list[dict]:
    limit = max(1, min(int(limit), 100))
    stmt = (
        select(m.AiQuery)
        .where(
            m.AiQuery.tenant_id == tenant_id,
            m.AiQuery.user_id == user_id,
        )
        .order_by(m.AiQuery.created_at.desc())
        .limit(limit)
    )
    stmt = apply_company_filter(stmt, m.AiQuery.company_id, company_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [serialize_query(r) for r in rows]


def serialize_query(row: m.AiQuery) -> dict:
    out = {
        "id": row.id,
        "message": row.message,
        "answer": row.answer,
        "intent": row.intent,
        "data": row.payload or {},
        "created_at": row.created_at,
    }
    if getattr(row, "company_id", None):
        out["company_id"] = row.company_id
    return out
