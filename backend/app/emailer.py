"""Outbound email via SMTP with safe development fallback."""

from __future__ import annotations

import asyncio
import html
import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any

from fastapi import HTTPException

from app.config import settings
from app.email_settings import SmtpConfig, resolve_smtp_config

logger = logging.getLogger(__name__)

# In-memory outbox for tests / development inspection
_DEV_OUTBOX: list[dict[str, Any]] = []


@dataclass
class EmailResult:
    sent: bool
    mode: str  # smtp | console | disabled
    message_id: str | None = None
    error: str | None = None
    recipients: list[str] = field(default_factory=list)


def clear_dev_outbox() -> None:
    _DEV_OUTBOX.clear()


def get_dev_outbox() -> list[dict[str, Any]]:
    return list(_DEV_OUTBOX)


def smtp_configured(tenant: Any | None = None) -> bool:
    return resolve_smtp_config(tenant).configured


def email_status(tenant: Any | None = None) -> dict:
    from app.email_settings import email_status as _email_status

    return _email_status(tenant)


def _delivery_mode(cfg: SmtpConfig | None = None) -> str:
    c = cfg or resolve_smtp_config(None)
    if not c.enabled:
        return "disabled"
    if c.configured:
        return "smtp"
    return "console"


def render_branded_html(
    *,
    body_html: str,
    company_name: str | None = None,
    tenant: Any | None = None,
    title: str | None = None,
) -> str:
    """Wrap inner HTML in a tenant-branded email chrome (logo, header, footer).

    Uses company name + optional ``print_branding`` header/footer and logo from the
    tenant record. Safe for console outbox inspection (logo as data-URI JPEG).
    """
    from app.print_branding import load_logo_jpeg, print_branding_settings

    company = (
        (company_name or getattr(tenant, "company_name", None) or "RIBDIGI ERP") or "RIBDIGI ERP"
    ).strip()
    company_esc = html.escape(company)
    branding = print_branding_settings(tenant)
    header = str(branding.get("header_text") or "").strip()
    footer = str(branding.get("footer_text") or "").strip()

    logo_html = ""
    logo = None
    if tenant is not None and getattr(tenant, "logo_url", None):
        logo = load_logo_jpeg(tenant, max_width_px=240, max_height_px=80)
    if logo:
        import base64

        jpeg, width_px, height_px = logo
        b64 = base64.b64encode(jpeg).decode("ascii")
        logo_html = (
            f'<img class="ribdigi-email-logo" src="data:image/jpeg;base64,{b64}" '
            f'width="{int(width_px)}" height="{int(height_px)}" alt="{company_esc}" '
            'style="display:block;max-width:240px;height:auto;margin:0 auto 12px;" />'
        )

    header_html = (
        f'<p class="ribdigi-email-header" style="margin:8px 0 0;color:#cbd5e1;font-size:13px;">'
        f"{html.escape(header)}</p>"
        if header
        else ""
    )
    footer_html = (
        f'<p class="ribdigi-email-footer" style="margin:0 0 8px;color:#64748b;font-size:12px;">'
        f"{html.escape(footer)}</p>"
        if footer
        else ""
    )
    title_html = (
        f'<h1 style="margin:0 0 16px;font-size:20px;line-height:1.3;color:#0f172a;">'
        f"{html.escape(title)}</h1>"
        if title
        else ""
    )

    return (
        "<!DOCTYPE html>"
        '<html lang="en"><head><meta charset="utf-8"/>'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
        f"<title>{html.escape(title or company)}</title></head>"
        '<body style="margin:0;padding:0;background:#f1f5f9;">'
        '<table role="presentation" class="ribdigi-email-brand" width="100%" cellspacing="0" '
        'cellpadding="0" style="background:#f1f5f9;padding:24px 12px;">'
        "<tr><td align=\"center\">"
        '<table role="presentation" width="600" cellspacing="0" cellpadding="0" '
        'style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;'
        'overflow:hidden;border:1px solid #e2e8f0;">'
        '<tr><td style="padding:20px 24px;background:#0f172a;color:#ffffff;text-align:center;'
        'font-family:Arial,Helvetica,sans-serif;">'
        f"{logo_html}"
        f'<div class="ribdigi-email-company" style="font-size:18px;font-weight:700;'
        f'letter-spacing:.02em;">{company_esc}</div>'
        f"{header_html}"
        "</td></tr>"
        '<tr><td style="padding:24px;font-family:Arial,Helvetica,sans-serif;color:#0f172a;'
        'font-size:14px;line-height:1.55;">'
        f"{title_html}{body_html}"
        "</td></tr>"
        '<tr><td style="padding:16px 24px;background:#f8fafc;border-top:1px solid #e2e8f0;'
        'text-align:center;font-family:Arial,Helvetica,sans-serif;">'
        f"{footer_html}"
        '<p style="margin:0;color:#94a3b8;font-size:11px;">Sent via RIBDIGI ERP</p>'
        "</td></tr></table></td></tr></table></body></html>"
    )


def _split_content_type(content_type: str | None) -> tuple[str, str]:
    raw = (content_type or "application/octet-stream").strip()
    if "/" not in raw:
        return "application", "octet-stream"
    maintype, subtype = raw.split("/", 1)
    return maintype.strip() or "application", subtype.strip() or "octet-stream"


def _attach_files(msg: EmailMessage, attachments: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Attach binary files; return lightweight metadata for outbox/logging."""
    meta: list[dict[str, Any]] = []
    for item in attachments or []:
        filename = str(item.get("filename") or "attachment.bin")
        content = item.get("content")
        if content is None:
            continue
        if isinstance(content, str):
            raw = content.encode("utf-8")
        else:
            raw = bytes(content)
        maintype, subtype = _split_content_type(item.get("content_type"))
        msg.add_attachment(raw, maintype=maintype, subtype=subtype, filename=filename)
        meta.append(
            {
                "filename": filename,
                "content_type": f"{maintype}/{subtype}",
                "size_bytes": len(raw),
            }
        )
    return meta


def build_message(
    *,
    to: str | list[str],
    subject: str,
    text_body: str,
    html_body: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    cfg: SmtpConfig | None = None,
) -> EmailMessage:
    recipients = [to] if isinstance(to, str) else list(to)
    if not recipients:
        raise HTTPException(status_code=400, detail="At least one recipient is required")
    c = cfg or resolve_smtp_config(None)
    msg = EmailMessage()
    msg["Subject"] = subject
    from_name = (c.from_name or "RIBDIGI ERP").strip()
    from_email = (c.from_email or "noreply@localhost").strip()
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = ", ".join(recipients)
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    _attach_files(msg, attachments)
    return msg


def _smtp_send_sync(msg: EmailMessage, cfg: SmtpConfig) -> None:
    host = cfg.host
    port = int(cfg.port)
    timeout = float(settings.SMTP_TIMEOUT_SECONDS)
    user = (cfg.username or "").strip() or None
    password = cfg.password or None

    if cfg.use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as server:
            if user and password:
                server.login(user, password)
            server.send_message(msg)
        return

    with smtplib.SMTP(host, port, timeout=timeout) as server:
        server.ehlo()
        if cfg.use_tls:
            context = ssl.create_default_context()
            server.starttls(context=context)
            server.ehlo()
        if user and password:
            server.login(user, password)
        server.send_message(msg)


async def send_email(
    *,
    to: str | list[str],
    subject: str,
    text_body: str,
    html_body: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    tenant: Any | None = None,
    cfg: SmtpConfig | None = None,
) -> EmailResult:
    recipients = [to] if isinstance(to, str) else [r for r in to if r]
    c = cfg or resolve_smtp_config(tenant)
    mode = _delivery_mode(c)
    if mode == "disabled":
        return EmailResult(sent=False, mode="disabled", recipients=recipients)

    msg = build_message(
        to=recipients,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        attachments=attachments,
        cfg=c,
    )
    attachment_meta = [
        {
            "filename": str(a.get("filename") or "attachment.bin"),
            "content_type": a.get("content_type") or "application/octet-stream",
            "size_bytes": len(a.get("content") or b"")
            if not isinstance(a.get("content"), str)
            else len(str(a.get("content")).encode("utf-8")),
        }
        for a in (attachments or [])
        if a.get("content") is not None
    ]
    record = {
        "to": recipients,
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
        "attachments": attachment_meta,
        "mode": mode,
    }

    if mode == "console":
        _DEV_OUTBOX.append(record)
        logger.info("EMAIL console to=%s subject=%s", recipients, subject)
        return EmailResult(sent=True, mode="console", recipients=recipients)

    try:
        await asyncio.to_thread(_smtp_send_sync, msg, c)
        _DEV_OUTBOX.append({**record, "delivered": True})
        return EmailResult(sent=True, mode="smtp", recipients=recipients)
    except Exception as exc:
        logger.exception("SMTP send failed")
        _DEV_OUTBOX.append({**record, "delivered": False, "error": str(exc)})
        return EmailResult(sent=False, mode="smtp", recipients=recipients, error=str(exc)[:500])


def verification_link(token: str) -> str:
    base = (settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
    return f"{base}/verify-email?token={token}"


def password_reset_link(token: str) -> str:
    base = (settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
    return f"{base}/reset-password?token={token}"


async def send_verification_email(
    *, to: str, token: str, company_name: str | None = None, tenant: Any | None = None
) -> EmailResult:
    link = verification_link(token)
    company = company_name or getattr(tenant, "company_name", None) or "RIBDIGI ERP"
    subject = f"Verify your {company} email"
    text = (
        f"Welcome to {company}.\n\n"
        f"Verify your email by opening this link:\n{link}\n\n"
        f"If you did not create an account, ignore this message.\n"
    )
    inner = (
        f"<p>Welcome to <strong>{html.escape(company)}</strong>.</p>"
        f'<p><a href="{html.escape(link)}">Verify your email</a></p>'
        f"<p>Or paste: {html.escape(link)}</p>"
    )
    branded = render_branded_html(
        body_html=inner, company_name=company, tenant=tenant, title="Verify your email"
    )
    return await send_email(to=to, subject=subject, text_body=text, html_body=branded, tenant=tenant)


async def send_password_reset_email(*, to: str, token: str, tenant: Any | None = None) -> EmailResult:
    link = password_reset_link(token)
    company = getattr(tenant, "company_name", None) or "RIBDIGI ERP"
    subject = "Reset your RIBDIGI ERP password"
    text = (
        "A password reset was requested for your account.\n\n"
        f"Reset link (expires in 1 hour):\n{link}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    inner = (
        "<p>A password reset was requested for your account.</p>"
        f'<p><a href="{html.escape(link)}">Reset password</a></p>'
        f"<p>Or paste: {html.escape(link)}</p>"
    )
    branded = render_branded_html(
        body_html=inner, company_name=company, tenant=tenant, title="Password reset"
    )
    return await send_email(to=to, subject=subject, text_body=text, html_body=branded, tenant=tenant)


async def send_notification_email(
    *, to: str, title: str, message: str, category: str, tenant: Any | None = None
) -> EmailResult:
    subject = f"[RIBDIGI] {title}"
    text = f"{title}\n\n{message}\n\nCategory: {category}\n"
    company = getattr(tenant, "company_name", None) or "RIBDIGI ERP"
    inner = (
        f"<h3>{html.escape(title)}</h3>"
        f"<p>{html.escape(message)}</p>"
        f"<p><em>{html.escape(category)}</em></p>"
    )
    branded = render_branded_html(
        body_html=inner, company_name=company, tenant=tenant, title=title
    )
    return await send_email(to=to, subject=subject, text_body=text, html_body=branded, tenant=tenant)


def render_ai_insight_digest_bodies(
    *,
    company_name: str,
    insights: list[str],
    tenant: Any | None = None,
) -> tuple[str, str]:
    """Render the tenant-safe plain-text and HTML weekly digest."""
    company = (company_name or "RIBDIGI ERP").strip()
    notes = [str(note).strip() for note in insights if str(note).strip()]
    if not notes:
        notes = ["No urgent anomaly detected from the currently configured business rules."]

    text = "\n".join(
        [
            f"Weekly AI insight digest — {company}",
            "",
            *[f"{index}. {note}" for index, note in enumerate(notes, start=1)],
            "",
            "Open the RIBDIGI ERP dashboard to review the underlying business data.",
        ]
    )
    items = "".join(f"<li>{html.escape(note)}</li>" for note in notes)
    inner = (
        f"<ol>{items}</ol>"
        "<p>Open the RIBDIGI ERP dashboard to review the underlying business data.</p>"
    )
    html_body = render_branded_html(
        body_html=inner,
        company_name=company,
        tenant=tenant,
        title=f"Weekly AI insight digest — {company}",
    )
    return text, html_body


async def send_ai_insight_digest_email(
    *,
    to: str,
    company_name: str,
    insights: list[str],
    tenant: Any | None = None,
) -> EmailResult:
    text, html_body = render_ai_insight_digest_bodies(
        company_name=company_name,
        insights=insights,
        tenant=tenant,
    )
    return await send_email(
        to=to,
        subject=f"Weekly AI insight digest — {company_name}",
        text_body=text,
        html_body=html_body,
        tenant=tenant,
    )


def _fmt_money(value: Any) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def render_quotation_bodies(
    *,
    company_name: str,
    currency: str,
    customer_name: str,
    quotation: dict[str, Any],
    tenant: Any | None = None,
) -> tuple[str, str]:
    number = quotation.get("quotation_number") or ""
    valid = quotation.get("valid_until")
    valid_s = str(valid)[:10] if valid else "—"
    lines = [
        f"Quotation {number}",
        f"From: {company_name}",
        f"To: {customer_name}",
        f"Valid until: {valid_s}",
        "",
        "Items:",
    ]
    html_rows = []
    for item in quotation.get("items") or []:
        desc = item.get("product_id") or "Item"
        if item.get("variant_id"):
            desc = f"{desc} (variant {item['variant_id'][:8]})"
        qty = item.get("quantity")
        price = _fmt_money(item.get("unit_price"))
        total = _fmt_money(item.get("line_total"))
        lines.append(f"  - {desc}: qty {qty} × {currency} {price} = {currency} {total}")
        html_rows.append(
            f"<tr><td>{html.escape(str(desc))}</td><td>{html.escape(str(qty))}</td>"
            f"<td>{html.escape(currency)} {price}</td><td>{html.escape(currency)} {total}</td></tr>"
        )
    lines.extend(
        [
            "",
            f"Subtotal: {currency} {_fmt_money(quotation.get('subtotal'))}",
            f"Tax: {currency} {_fmt_money(quotation.get('tax_amount'))}",
            f"Discount: {currency} {_fmt_money(quotation.get('discount_amount'))}",
            f"Total: {currency} {_fmt_money(quotation.get('total_amount'))}",
        ]
    )
    if quotation.get("notes"):
        lines.extend(["", f"Notes: {quotation['notes']}"])
    lines.append("\nThank you for your business.")
    text = "\n".join(lines)
    inner = (
        f"<p>From <strong>{html.escape(company_name)}</strong><br/>"
        f"To {html.escape(str(customer_name))}<br/>Valid until {html.escape(valid_s)}</p>"
        '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;">'
        "<thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Line</th></tr></thead>"
        f"<tbody>{''.join(html_rows)}</tbody></table>"
        f"<p>Subtotal: {html.escape(currency)} {_fmt_money(quotation.get('subtotal'))}<br/>"
        f"Tax: {html.escape(currency)} {_fmt_money(quotation.get('tax_amount'))}<br/>"
        f"Discount: {html.escape(currency)} {_fmt_money(quotation.get('discount_amount'))}<br/>"
        f"<strong>Total: {html.escape(currency)} {_fmt_money(quotation.get('total_amount'))}</strong></p>"
    )
    if quotation.get("notes"):
        inner += f"<p>Notes: {html.escape(str(quotation['notes']))}</p>"
    branded = render_branded_html(
        body_html=inner,
        company_name=company_name,
        tenant=tenant,
        title=f"Quotation {number}",
    )
    return text, branded


async def send_quotation_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    customer_name: str,
    quotation: dict[str, Any],
    tenant: Any | None = None,
) -> EmailResult:
    number = quotation.get("quotation_number") or ""
    subject = f"Quotation {number} from {company_name}"
    text, html_body = render_quotation_bodies(
        company_name=company_name,
        currency=currency,
        customer_name=customer_name,
        quotation=quotation,
        tenant=tenant,
    )
    return await send_email(
        to=to, subject=subject, text_body=text, html_body=html_body, tenant=tenant
    )


def render_purchase_order_bodies(
    *,
    company_name: str,
    currency: str,
    supplier_name: str,
    purchase_order: dict[str, Any],
    tenant: Any | None = None,
) -> tuple[str, str]:
    number = purchase_order.get("po_number") or ""
    due = purchase_order.get("due_date")
    due_s = str(due)[:10] if due else "—"
    delivery_address = (purchase_order.get("delivery_address") or "").strip()
    lines = [
        f"Purchase Order {number}",
        f"From: {company_name}",
        f"To: {supplier_name}",
        f"Due date: {due_s}",
    ]
    if delivery_address:
        lines.append(f"Delivery address: {delivery_address}")
    lines.extend(
        [
            "",
            "Items:",
        ]
    )
    html_rows = []
    for item in purchase_order.get("items") or []:
        desc = item.get("product_id") or "Item"
        qty = item.get("quantity")
        price = _fmt_money(item.get("unit_price"))
        total = _fmt_money(item.get("line_total"))
        tax = _fmt_money(item.get("tax_rate"))
        disc = float(item.get("discount") or 0)
        disc_s = f" discount {currency} {_fmt_money(disc)}" if disc else ""
        lines.append(
            f"  - {desc}: qty {qty} × {currency} {price} (tax {tax}%{disc_s}) = {currency} {total}"
        )
        disc_cell = _fmt_money(disc) if disc else "—"
        html_rows.append(
            f"<tr><td>{html.escape(str(desc))}</td><td>{html.escape(str(qty))}</td>"
            f"<td>{html.escape(currency)} {price}</td>"
            f"<td>{tax}%</td><td>{html.escape(currency)} {disc_cell}</td>"
            f"<td>{html.escape(currency)} {total}</td></tr>"
        )
    lines.extend(
        [
            "",
            f"Subtotal: {currency} {_fmt_money(purchase_order.get('subtotal'))}",
            f"Tax: {currency} {_fmt_money(purchase_order.get('tax_amount'))}",
            f"Total: {currency} {_fmt_money(purchase_order.get('total_amount'))}",
        ]
    )
    if purchase_order.get("notes"):
        lines.extend(["", f"Notes: {purchase_order['notes']}"])
    lines.append("\nPlease confirm this purchase order.")
    text = "\n".join(lines)
    delivery_html = (
        f"<br/>Delivery address: {html.escape(delivery_address)}" if delivery_address else ""
    )
    inner = (
        f"<p>From <strong>{html.escape(company_name)}</strong><br/>"
        f"To {html.escape(str(supplier_name))}<br/>Due {html.escape(due_s)}"
        f"{delivery_html}</p>"
        '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;">'
        "<thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Tax</th><th>Discount</th><th>Line</th></tr></thead>"
        f"<tbody>{''.join(html_rows)}</tbody></table>"
        f"<p>Subtotal: {html.escape(currency)} {_fmt_money(purchase_order.get('subtotal'))}<br/>"
        f"Tax: {html.escape(currency)} {_fmt_money(purchase_order.get('tax_amount'))}<br/>"
        f"<strong>Total: {html.escape(currency)} {_fmt_money(purchase_order.get('total_amount'))}</strong></p>"
    )
    if purchase_order.get("notes"):
        inner += f"<p>Notes: {html.escape(str(purchase_order['notes']))}</p>"
    branded = render_branded_html(
        body_html=inner,
        company_name=company_name,
        tenant=tenant,
        title=f"Purchase Order {number}",
    )
    return text, branded


async def send_purchase_order_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    supplier_name: str,
    purchase_order: dict[str, Any],
    amended: bool = False,
    tenant: Any | None = None,
) -> EmailResult:
    number = purchase_order.get("po_number") or ""
    rev = purchase_order.get("revision_no")
    if amended and rev:
        subject = f"Purchase Order {number} (amended rev.{rev}) from {company_name}"
    else:
        subject = f"Purchase Order {number} from {company_name}"
    text, html_body = render_purchase_order_bodies(
        company_name=company_name,
        currency=currency,
        supplier_name=supplier_name,
        purchase_order=purchase_order,
        tenant=tenant,
    )
    return await send_email(
        to=to, subject=subject, text_body=text, html_body=html_body, tenant=tenant
    )


def render_sales_invoice_bodies(
    *,
    company_name: str,
    currency: str,
    customer_name: str,
    invoice: dict[str, Any],
    tenant: Any | None = None,
) -> tuple[str, str]:
    number = invoice.get("invoice_number") or ""
    due = invoice.get("due_date")
    due_s = str(due)[:10] if due else "—"
    lines = [
        f"Sales Invoice {number}",
        f"From: {company_name}",
        f"To: {customer_name}",
        f"Due date: {due_s}",
        "",
        "Items:",
    ]
    html_rows = []
    for item in invoice.get("items") or []:
        desc = item.get("product_id") or "Item"
        if item.get("variant_id"):
            desc = f"{desc} (variant {item['variant_id'][:8]})"
        qty = item.get("quantity")
        price = _fmt_money(item.get("unit_price"))
        total = _fmt_money(item.get("line_total"))
        tax = _fmt_money(item.get("tax_rate"))
        lines.append(
            f"  - {desc}: qty {qty} × {currency} {price} (tax {tax}%) = {currency} {total}"
        )
        html_rows.append(
            f"<tr><td>{html.escape(str(desc))}</td><td>{html.escape(str(qty))}</td>"
            f"<td>{html.escape(currency)} {price}</td>"
            f"<td>{tax}%</td><td>{html.escape(currency)} {total}</td></tr>"
        )
    lines.extend(
        [
            "",
            f"Subtotal: {currency} {_fmt_money(invoice.get('subtotal'))}",
            f"Tax: {currency} {_fmt_money(invoice.get('tax_amount'))}",
            f"Discount: {currency} {_fmt_money(invoice.get('discount_amount'))}",
            f"Total: {currency} {_fmt_money(invoice.get('total_amount'))}",
            f"Paid: {currency} {_fmt_money(invoice.get('paid_amount'))}",
            f"Balance due: {currency} {_fmt_money(invoice.get('balance_due'))}",
        ]
    )
    if invoice.get("notes"):
        lines.extend(["", f"Notes: {invoice['notes']}"])
    lines.append("\nThank you for your business.")
    text = "\n".join(lines)
    inner = (
        f"<p>From <strong>{html.escape(company_name)}</strong><br/>"
        f"To {html.escape(str(customer_name))}<br/>Due {html.escape(due_s)}</p>"
        '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;">'
        "<thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Tax</th><th>Line</th></tr></thead>"
        f"<tbody>{''.join(html_rows)}</tbody></table>"
        f"<p>Subtotal: {html.escape(currency)} {_fmt_money(invoice.get('subtotal'))}<br/>"
        f"Tax: {html.escape(currency)} {_fmt_money(invoice.get('tax_amount'))}<br/>"
        f"Discount: {html.escape(currency)} {_fmt_money(invoice.get('discount_amount'))}<br/>"
        f"<strong>Total: {html.escape(currency)} {_fmt_money(invoice.get('total_amount'))}</strong><br/>"
        f"Paid: {html.escape(currency)} {_fmt_money(invoice.get('paid_amount'))}<br/>"
        f"Balance due: {html.escape(currency)} {_fmt_money(invoice.get('balance_due'))}</p>"
    )
    if invoice.get("notes"):
        inner += f"<p>Notes: {html.escape(str(invoice['notes']))}</p>"
    branded = render_branded_html(
        body_html=inner,
        company_name=company_name,
        tenant=tenant,
        title=f"Sales Invoice {number}",
    )
    return text, branded


async def send_sales_invoice_email(
    *,
    to: str,
    company_name: str,
    currency: str,
    customer_name: str,
    invoice: dict[str, Any],
    tenant: Any | None = None,
) -> EmailResult:
    number = invoice.get("invoice_number") or ""
    subject = f"Invoice {number} from {company_name}"
    text, html_body = render_sales_invoice_bodies(
        company_name=company_name,
        currency=currency,
        customer_name=customer_name,
        invoice=invoice,
        tenant=tenant,
    )
    return await send_email(
        to=to, subject=subject, text_body=text, html_body=html_body, tenant=tenant
    )


async def send_test_email(*, to: str, tenant: Any | None = None) -> EmailResult:
    c = resolve_smtp_config(tenant)
    if not c.enabled:
        raise HTTPException(status_code=400, detail="EMAIL_ENABLED is false")
    mode = _delivery_mode(c)
    if not c.configured and mode != "console":
        raise HTTPException(status_code=400, detail="SMTP is not configured")
    company = getattr(tenant, "company_name", None) or "RIBDIGI ERP"
    inner = (
        f"<p>This is a test email from <strong>{html.escape(company)}</strong>. "
        "SMTP delivery is working.</p>"
        "<p>Your company logo, print header, and footer (Company → Print branding) "
        "appear in the chrome of outbound emails.</p>"
    )
    branded = render_branded_html(
        body_html=inner,
        company_name=company,
        tenant=tenant,
        title="Test email",
    )
    return await send_email(
        to=to,
        subject="RIBDIGI ERP test email",
        text_body=(
            f"This is a test email from {company}. SMTP delivery is working.\n"
            "Your company logo, print header, and footer appear on outbound emails.\n"
        ),
        html_body=branded,
        cfg=c,
        tenant=tenant,
    )
