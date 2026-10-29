"""Shared send helpers for commercial documents (no invented addresses)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import emailer
from app import purchase_requests as purchase_requests_svc
from app import purchasing as purchasing_svc
from app import sales as sales_svc
from app import sales_docs as sales_docs_svc
from app.document_print import get_customer_payment, get_supplier_payment
from app.honesty import money_json


def require_recipient(
    to: str | None,
    party_email: str | None,
    *,
    missing: str,
) -> str:
    recipient = (to or party_email or "").strip()
    if not recipient:
        raise HTTPException(status_code=400, detail=missing)
    return recipient


def _refuse_cancelled(status: str | None, *, kind: str) -> None:
    if (status or "").strip().lower() == "cancelled":
        raise HTTPException(status_code=409, detail=f"Cannot email a cancelled {kind}")


async def _tenant_context(db: AsyncSession, tenant_id: str) -> tuple[m.Tenant | None, str, str]:
    tenant = await db.get(m.Tenant, tenant_id)
    company = (tenant.company_name if tenant else None) or "RIBDIGI ERP"
    currency = (tenant.currency if tenant else None) or "GHS"
    return tenant, company, currency


async def finish_send(result: emailer.EmailResult, *, recipient: str) -> dict[str, Any]:
    if not result.sent:
        if result.mode == "disabled":
            raise HTTPException(status_code=503, detail="Email delivery is disabled")
        raise HTTPException(status_code=502, detail=result.error or "Email send failed")
    now = datetime.utcnow()
    return {
        "sent": result.sent,
        "mode": result.mode,
        "to": recipient,
        "emailed_at": now.isoformat(),
    }


async def send_sales_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    order_id: str,
    to: str | None = None,
) -> tuple[m.SalesOrder, dict]:
    order = await sales_docs_svc.get_order(db, tenant_id, order_id)
    _refuse_cancelled(order.status, kind="sales order")
    customer = await sales_svc.get_customer(db, tenant_id, order.customer_id)
    recipient = require_recipient(
        to,
        getattr(customer, "email", None),
        missing="This customer has no email address. Add one to the customer, or type an address in Email to.",
    )
    tenant, company, currency = await _tenant_context(db, tenant_id)
    payload = await sales_docs_svc.serialize_order(db, order)
    result = await emailer.send_sales_order_email(
        to=recipient,
        company_name=company,
        currency=currency,
        customer_name=customer.name,
        order=payload,
        tenant=tenant,
    )
    delivery = await finish_send(result, recipient=recipient)
    return order, delivery


async def send_sales_return(
    db: AsyncSession,
    *,
    tenant_id: str,
    return_id: str,
    to: str | None = None,
) -> tuple[m.SalesReturn, dict]:
    ret = await sales_docs_svc.get_return(db, tenant_id, return_id)
    _refuse_cancelled(ret.status, kind="sales return")
    customer = None
    if ret.customer_id:
        customer = await sales_svc.get_customer(db, tenant_id, ret.customer_id)
    recipient = require_recipient(
        to,
        getattr(customer, "email", None) if customer else None,
        missing="This customer has no email address. Add one to the customer, or type an address in Email to.",
    )
    tenant, company, currency = await _tenant_context(db, tenant_id)
    payload = await sales_docs_svc.serialize_return(db, ret)
    result = await emailer.send_sales_return_email(
        to=recipient,
        company_name=company,
        currency=currency,
        customer_name=(customer.name if customer else "Walk-in"),
        ret=payload,
        tenant=tenant,
    )
    delivery = await finish_send(result, recipient=recipient)
    return ret, delivery


async def send_customer_payment(
    db: AsyncSession,
    *,
    tenant_id: str,
    payment_id: str,
    to: str | None = None,
) -> tuple[m.CustomerPayment, dict]:
    payment = await get_customer_payment(db, tenant_id, payment_id)
    customer = await sales_svc.get_customer(db, tenant_id, payment.customer_id)
    recipient = require_recipient(
        to,
        getattr(customer, "email", None),
        missing="This customer has no email address. Add one to the customer, or type an address in Email to.",
    )
    tenant, company, currency = await _tenant_context(db, tenant_id)
    currency = (getattr(payment, "currency", None) or "").strip() or currency
    invoice_number = ""
    if payment.sales_invoice_id:
        invoice = await db.get(m.SalesInvoice, payment.sales_invoice_id)
        if invoice and invoice.tenant_id == tenant_id:
            invoice_number = invoice.invoice_number or ""
    payload = {
        "payment_number": payment.payment_number,
        "amount": money_json(payment.amount),
        "payment_method": payment.payment_method,
        "reference": payment.reference,
        "notes": payment.notes,
        "created_at": payment.created_at,
        "invoice_number": invoice_number,
    }
    result = await emailer.send_customer_payment_email(
        to=recipient,
        company_name=company,
        currency=currency,
        customer_name=customer.name,
        payment=payload,
        tenant=tenant,
    )
    delivery = await finish_send(result, recipient=recipient)
    return payment, delivery


async def send_customer_statement(
    db: AsyncSession,
    *,
    tenant_id: str,
    customer_id: str,
    to: str | None = None,
) -> tuple[dict, dict]:
    """Email the statement of account with the A4 PDF attached."""
    import html as html_mod

    from app import credit as credit_svc
    from app.document_print import build_customer_statement_print, to_document_a4_pdf

    statement = await credit_svc.customer_statement(db, tenant_id, customer_id)
    customer = await sales_svc.get_customer(db, tenant_id, customer_id)
    recipient = require_recipient(
        to,
        getattr(customer, "email", None),
        missing="This customer has no email address. Add one to the customer, or type an address in Email to.",
    )
    tenant, company, currency = await _tenant_context(db, tenant_id)
    payload = build_customer_statement_print(statement, tenant=tenant)
    owed = f"{payload.get('currency') or currency} {money_json(statement.get('outstanding_balance') or 0)}"
    text = (
        f"Dear {customer.name},\n\nPlease find your statement of account from {company} attached.\n"
        f"Amount owed: {owed}.\n\nThank you."
    )
    inner = (
        f"<p>Dear {html_mod.escape(customer.name)},</p>"
        f"<p>Please find your statement of account from <strong>{html_mod.escape(company)}</strong> attached.</p>"
        f"<p>Amount owed: <strong>{html_mod.escape(owed)}</strong></p><p>Thank you.</p>"
    )
    result = await emailer.send_email(
        to=recipient,
        subject=f"Statement of account from {company}".strip(),
        text_body=text,
        html_body=emailer.render_branded_html(body_html=inner, company_name=company, tenant=tenant, title="Statement of account"),
        attachments=[{
            "filename": f"statement_{customer.name}.pdf".replace(" ", "_"),
            "content": to_document_a4_pdf(payload),
            "content_type": "application/pdf",
        }],
        tenant=tenant,
    )
    delivery = await finish_send(result, recipient=recipient)
    return statement, delivery


async def send_purchase_request(
    db: AsyncSession,
    *,
    tenant_id: str,
    request_id: str,
    to: str | None = None,
) -> tuple[m.PurchaseRequest, dict]:
    row = await purchase_requests_svc.get_request(db, tenant_id, request_id)
    _refuse_cancelled(row.status, kind="purchase request")
    supplier_email = None
    supplier_name = ""
    if row.preferred_supplier_id:
        supplier = await purchasing_svc.get_supplier(db, tenant_id, row.preferred_supplier_id)
        supplier_email = getattr(supplier, "email", None)
        supplier_name = supplier.name
    requester_email = None
    if row.created_by:
        user = await db.get(m.User, row.created_by)
        if user and user.tenant_id == tenant_id:
            requester_email = user.email
            if not supplier_name:
                supplier_name = user.full_name or user.email or "Requester"
    recipient = require_recipient(
        to,
        supplier_email or requester_email,
        missing="This purchase request has no requester or preferred-supplier email. Add one, or type an address in Email to.",
    )
    tenant, company, currency = await _tenant_context(db, tenant_id)
    payload = await purchase_requests_svc.serialize_request(db, row)
    result = await emailer.send_purchase_request_email(
        to=recipient,
        company_name=company,
        currency=currency,
        party_name=supplier_name or "Requester",
        request=payload,
        tenant=tenant,
    )
    delivery = await finish_send(result, recipient=recipient)
    return row, delivery


async def send_grn(
    db: AsyncSession,
    *,
    tenant_id: str,
    grn_id: str,
    to: str | None = None,
) -> tuple[m.GoodsReceipt, dict]:
    grn = await purchasing_svc.get_grn(db, tenant_id, grn_id)
    supplier = await purchasing_svc.get_supplier(db, tenant_id, grn.supplier_id)
    recipient = require_recipient(
        to,
        getattr(supplier, "email", None),
        missing="This supplier has no email address. Add one to the supplier, or type an address in Email to.",
    )
    tenant, company, currency = await _tenant_context(db, tenant_id)
    payload = await purchasing_svc.serialize_grn(db, grn)
    if grn.purchase_order_id:
        po = await db.get(m.PurchaseOrder, grn.purchase_order_id)
        if po and po.tenant_id == tenant_id:
            payload["po_number"] = po.po_number
    result = await emailer.send_grn_email(
        to=recipient,
        company_name=company,
        currency=currency,
        supplier_name=supplier.name,
        grn=payload,
        tenant=tenant,
    )
    delivery = await finish_send(result, recipient=recipient)
    return grn, delivery


async def send_purchase_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    invoice_id: str,
    to: str | None = None,
) -> tuple[m.PurchaseInvoice, dict]:
    inv = await purchasing_svc.get_purchase_invoice(db, tenant_id, invoice_id)
    _refuse_cancelled(inv.status, kind="supplier bill")
    supplier = await purchasing_svc.get_supplier(db, tenant_id, inv.supplier_id)
    recipient = require_recipient(
        to,
        getattr(supplier, "email", None),
        missing="This supplier has no email address. Add one to the supplier, or type an address in Email to.",
    )
    tenant, company, currency = await _tenant_context(db, tenant_id)
    currency = (getattr(inv, "currency", None) or "").strip() or currency
    payload = await purchasing_svc.serialize_purchase_invoice(db, inv)
    result = await emailer.send_purchase_invoice_email(
        to=recipient,
        company_name=company,
        currency=currency,
        supplier_name=supplier.name,
        invoice=payload,
        tenant=tenant,
    )
    delivery = await finish_send(result, recipient=recipient)
    return inv, delivery


async def send_purchase_return(
    db: AsyncSession,
    *,
    tenant_id: str,
    return_id: str,
    to: str | None = None,
) -> tuple[m.PurchaseReturn, dict]:
    ret = await purchasing_svc.get_purchase_return(db, tenant_id, return_id)
    _refuse_cancelled(ret.status, kind="purchase return")
    supplier = await purchasing_svc.get_supplier(db, tenant_id, ret.supplier_id)
    recipient = require_recipient(
        to,
        getattr(supplier, "email", None),
        missing="This supplier has no email address. Add one to the supplier, or type an address in Email to.",
    )
    tenant, company, currency = await _tenant_context(db, tenant_id)
    payload = await purchasing_svc.serialize_purchase_return(db, ret)
    result = await emailer.send_purchase_return_email(
        to=recipient,
        company_name=company,
        currency=currency,
        supplier_name=supplier.name,
        ret=payload,
        tenant=tenant,
    )
    delivery = await finish_send(result, recipient=recipient)
    return ret, delivery


async def send_supplier_payment(
    db: AsyncSession,
    *,
    tenant_id: str,
    payment_id: str,
    to: str | None = None,
) -> tuple[m.SupplierPayment, dict]:
    payment = await get_supplier_payment(db, tenant_id, payment_id)
    supplier = await purchasing_svc.get_supplier(db, tenant_id, payment.supplier_id)
    recipient = require_recipient(
        to,
        getattr(supplier, "email", None),
        missing="This supplier has no email address. Add one to the supplier, or type an address in Email to.",
    )
    tenant, company, currency = await _tenant_context(db, tenant_id)
    currency = (getattr(payment, "currency", None) or "").strip() or currency
    bill_number = ""
    if payment.purchase_invoice_id:
        bill = await db.get(m.PurchaseInvoice, payment.purchase_invoice_id)
        if bill and bill.tenant_id == tenant_id:
            bill_number = bill.invoice_number or ""
    payload = {
        "payment_number": payment.payment_number,
        "amount": money_json(payment.amount),
        "payment_method": payment.payment_method,
        "reference": payment.reference,
        "notes": payment.notes,
        "created_at": payment.created_at,
        "bill_number": bill_number,
    }
    result = await emailer.send_supplier_payment_email(
        to=recipient,
        company_name=company,
        currency=currency,
        supplier_name=supplier.name,
        payment=payload,
        tenant=tenant,
    )
    delivery = await finish_send(result, recipient=recipient)
    return payment, delivery
